"""FORCE=1 is a real rebuild (issue #638): no layer cache, no stale base, no "available, skip".

The sweep's whole purpose is to prove the pins build. A `--force` that still reads the registry
cache re-tags the previous layers instead of compiling, so the run looks green having built
nothing — which is exactly what it did before this change.
"""

from __future__ import annotations

import subprocess
import types
import urllib.error
import urllib.request

from email.message import Message
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import scripts.engine_image as ei  # noqa: E402
from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)


def _spec() -> dict:
    return {"id": "llama.cpp", "tag": "llgenie/llama-cpp:23924232-3932631f-cpu", "variant": "cpu",
            "backend": "cpu", "dockerfile": "containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu",
            "params_file": "containers/engines/params/llama.cpp.json"}


def _patch_shell(monkeypatch, sh) -> None:
    """Record BOTH shell policies on `engine_image`.

    The long `buildx build` step goes through the STREAMING `_sh_live` (issue #2089) while the short
    probes/pulls/tags stay on the capturing `_sh` — a recorder installed on `_sh` alone would see no
    build command at all.
    """
    monkeypatch.setattr(ei, "_sh", sh)
    monkeypatch.setattr(ei, "_sh_live", sh)


def _record(monkeypatch, rc: int = 0) -> list[list[str]]:
    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, rc)

    # Both policies record into the ONE list (see `_patch_shell`), so `calls` is one ordered list.
    _patch_shell(monkeypatch, sh)
    return calls


def _package_state(monkeypatch, published: bool) -> list[str]:
    """Stub the PACKAGE-existence probe (`_package_published`, issue #3017) and record its calls.

    The write side's ladder asks a second registry question when the cache ref is absent. A test
    that does not stub it would ask the real GHCR API over the network, so every test that drives
    the absent-cache path stubs it here — `published=False` keeps the #1842/#1880 tolerance intent
    pinned (the engine's package is not on the registry yet), `published=True` pins the seeding case.
    """
    seen: list[str] = []

    def probe(ref: str) -> bool:
        seen.append(ref)
        return published

    monkeypatch.setattr(ei, "_package_published", probe)
    return seen


def test_a_forced_build_passes_no_cache_and_drops_cache_from(monkeypatch, tmp_path):
    """`force=True` → `--no-cache`, and the registry cache is not read at all."""

    # Given a local (non-pushing) buildx call
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When  it is forced
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache",
               force=True)

    # Then  buildx gets --no-cache and no --cache-from
    build = calls[-1]
    assert "--no-cache" in build
    assert not any(a == "--cache-from" for a in build)
    # and, being a forced LOCAL build, it consults neither cache side, so the cache-existence
    # probe is never issued (issue #1880's single-probe contract: probe only when a side reads)
    assert not any(c[:4] == ["docker", "buildx", "imagetools", "inspect"] for c in calls)


def test_an_unforced_build_keeps_the_registry_cache(monkeypatch, tmp_path):
    """Without FORCE the cache is still read: unchanged layers are reused."""

    # Given a local buildx call
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When  it is NOT forced
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then  --cache-from is there, it does NOT write back, and --no-cache is not
    build = calls[-1]
    assert "--no-cache" not in build
    assert "type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache" in build
    assert not any(a == "--cache-to" for a in build)


def test_a_nonpush_unforced_build_writes_back_the_cache_only_when_privileged(monkeypatch, tmp_path):
    """The verification-only sweep warms the shared cache for its NEXT run (#1694).

    `LLGENIE_CACHE_WRITE=1` turns the read-only local build into a read+write one, so an
    owner-guarded engine-build dispatch (push=false) leaves a warm cache behind instead of every
    fresh runner reading cold. The flag is the privilege boundary: without it the build is
    strictly read-only (the pre-#1694 behaviour, still the PR/fork/local one).
    """

    # Given a non-pushing, unforced build WITHOUT the privileged write flag (the fork/PR default)
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", False)

    # When  it builds and verifies
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then  the cache is read but never written back
    build = calls[-1]
    assert "type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache" in build
    assert not any(a == "--cache-to" for a in build)

    # Given the SAME build but with the privileged flag set (the owner-guarded engine-build dispatch)
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When  it builds and verifies
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then  the cache is read AND written back (mode=max), so the next cell run is warm
    build = calls[-1]
    assert "--no-cache" not in build
    assert "--cache-from" in build
    assert any(str(a).startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache")
               for a in build)
    any_to = [a for a in build if str(a).startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache,")]
    assert any_to and all("mode=max" in str(a) for a in any_to)


def test_a_cache_write_build_stays_on_the_container_builder(monkeypatch, tmp_path):
    """CACHE_WRITE=1 stops forcing the legacy `--builder default` (docker driver).

    The docker-driver `default` builder can read a registry cache but cannot EXPORT one
    ("Cache export is not supported for the docker driver" — measured on run
    41944882169, job 126975033244). When the owner-guarded engine-build dispatch (which
    sets LLGENIE_CACHE_WRITE=1 and creates a docker-container builder via
    setup-buildx-action) writes --cache-to type=registry, the build must stay on the ACTIVE
    container builder — never override it with --builder default. When the flag is unset
    (fork/PR/local), --builder default is still preferred so locally-loaded base images are
    seen (a fresh Colima has no default builder, so the inspect guard remains).
    """

    # Given a non-pushing build with the default builder present (inspect returns 0)
    def _driver(cache_write: bool) -> list[str]:
        calls = _record(monkeypatch)
        monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
        monkeypatch.setattr(ei, "CACHE_WRITE", cache_write)
        ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")
        return calls[-1]

    # When CACHE_WRITE is set (registry cache export is intended)
    build = _driver(True)
    # Then the docker-driver default builder must NOT override the container one
    assert "--builder" not in build, build
    assert any(str(a).startswith("type=registry,ref=") and "mode=max" in str(a) for a in build)

    # When CACHE_WRITE is unset (read-only fork/PR/local build)
    build = _driver(False)
    # Then the default builder is still preferred and the cache is read but not written
    assert "--builder" in build and "default" in build, build
    assert any(str(a).startswith("type=registry,ref=") for a in build)
    assert not any(a == "--cache-to" for a in build)


def test_a_missing_cache_image_builds_cold_not_red(monkeypatch, tmp_path):
    """A never-seeded registry cache must not red the cell (issues #1842, #1880, #3017).

    `--cache-from type=registry,ref=<missing>` makes buildx fail the whole build with
    `manifest unknown`, and `--cache-to type=registry,ref=<missing-package>` fails with
    `not found` when the engine's package is not on the registry yet. The read AND the
    write must tolerate the absence: when the probe finds no cache image AND the package
    is not published, the build proceeds cold (no --cache-from, no --cache-to) — a time
    cost, never a red cell. The package probe is stubbed ABSENT here: that is the state
    this tolerance pins (issue #3017 splits the absent-cache case in two).
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        # "imagetools inspect" is the cache-existence probe: report it absent (rc 1).
        # Every other command (including the build itself) succeeds.
        probe = any("imagetools" in a for a in cmd)
        return subprocess.CompletedProcess(cmd, 1 if probe else 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)
    _package_state(monkeypatch, published=False)

    # When an unforced build runs against a never-seeded cache whose package is unpublished
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then the build is COLD: no --cache-from and no --cache-to (no manifest-unknown /
    # not-found failure) — a missing cache is a time cost, never a red cell
    build = calls[-1]
    assert "--cache-from" not in build, build
    assert "--cache-to" not in build, build


def test_push_build_missing_cache_image_builds_cold_not_red(monkeypatch, tmp_path):
    """A never-seeded cache must not red a PUSH build either (issue #1880, #3017).

    The AC1 failing cell (`engine-build-tensorfold-cuda` in the default sweep, run
    `42280478755`) is a PUSH build: `_buildx(..., push=True)` runs the
    `if push and REGISTRY:` branch that appends `_cache_write_args`. The write-side
    tolerance must hold there too — when the engine's PACKAGE is absent from the
    registry (`buildcache-cuda: not found`), the push build proceeds cold with no
    `--cache-to` and no `--cache-from`, never red.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        # "imagetools inspect" is the cache-existence probe: report it absent (rc 1).
        # Every other command (the build, the pull, the tag) succeeds.
        probe = any("imagetools" in a for a in cmd)
        return subprocess.CompletedProcess(cmd, 1 if probe else 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)
    _package_state(monkeypatch, published=False)

    # When an unforced PUSH build runs against a never-seeded cache whose package is unpublished
    ei._buildx("llgenie/demo:t", str(tmp_path), True, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then the PUSH build is COLD: no --cache-from and no --cache-to — a missing
    # cache is a time cost, never a red cell, on the push path too
    build = next(c for c in calls if "--push" in c)
    assert "--cache-from" not in build, build
    assert "--cache-to" not in build, build
    assert "--push" in build, build


def test_push_build_present_cache_still_writes_when_privileged(monkeypatch, tmp_path):
    """A seeded cache ref is still written on a PUSH build (issue #1880).

    The write tolerance only suppresses the failure when the engine's package is
    absent from the registry. On the push path (`if push and REGISTRY:`), a present
    cache ref with `CACHE_WRITE=1` must still seed `--cache-to` for the next run —
    the write is not unconditionally dropped on push builds either.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        # "imagetools inspect" is the cache-existence probe: report it present (rc 0).
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When an unforced PUSH build runs against a seeded cache
    ei._buildx("llgenie/demo:t", str(tmp_path), True, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then the PUSH build still writes --cache-to (and reads --cache-from)
    build = next(c for c in calls if "--push" in c)
    assert "--cache-from" in build, build
    assert any(str(a).startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache")
               and "mode=max" in a for a in build), build


def test_cache_write_args_tolerates_missing_package(monkeypatch):
    """`_cache_write_args` returns [] when the engine's package is absent (issue #1880, #3017).

    The write-side tolerance is the whole point of #1881: a `--cache-to
    type=registry,ref=<missing-package>` fails the WHOLE build with `not found` when
    the engine's package is not on the registry yet. Direct unit test of the function
    (the push-path tests exercise it through `_buildx`; this pins the contract) with the
    package probe stubbed ABSENT — the state the tolerance is for.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        # "imagetools inspect" is the cache-existence probe: report it absent (rc 1).
        return subprocess.CompletedProcess(cmd, 1)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    seen = _package_state(monkeypatch, published=False)

    # When the engine's package is absent from the registry
    args = ei._cache_write_args("ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then no --cache-to is emitted (a cold build, never a red cell), and the ladder asked
    # the package question exactly once (issue #3017)
    assert args == [], args
    assert seen == ["ghcr.io/asimov-agent/llgenie/demo:buildcache"], seen


def test_cache_write_args_emits_cache_to_when_present(monkeypatch):
    """`_cache_write_args` emits --cache-to when the cache ref exists (issue #1880, #3017).

    The tolerance only suppresses the failure when the package is absent; a present
    cache ref must still be written (mode=max) for the next run — and it is written
    WITHOUT asking the package question at all: the probe budget (issue #3017) says a
    present cache never consults `_package_published`.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    def never_ask(ref: str) -> bool:
        raise AssertionError(f"a present cache ref must not consult the package probe: {ref}")

    monkeypatch.setattr(ei, "_package_published", never_ask)

    # When the engine's package IS on the registry
    args = ei._cache_write_args("ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then --cache-to is emitted with mode=max (the write still seeds the cache)
    assert args == ["--cache-to", "type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache,mode=max"], args


def test_cache_write_args_empty_without_registry(monkeypatch):
    """`_cache_write_args` returns [] when REGISTRY is unset (local build)."""

    monkeypatch.setattr(ei, "REGISTRY", "")

    assert ei._cache_write_args("ghcr.io/asimov-agent/llgenie/demo:buildcache") == []


def test_cache_exists_probe_contract(monkeypatch):
    """`_cache_exists` is the single probe the read (#1842) and write (#1880) sides share.

    It issues exactly one `docker buildx imagetools inspect` (the same registry manifest GET
    the `--cache-from`/`--cache-to` flags would) and maps a non-zero exit to "absent". No
    REGISTRY means no probe at all (local build). This is the direct contract test for the
    helper the two tolerances were refactored onto (issue #1880).
    """

    # present: probe rc 0 -> True, and the probe command is the documented one
    calls: list[list[str]] = []

    def sh_ok(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ei, "_sh", sh_ok)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    assert ei._cache_exists("ghcr.io/asimov-agent/llgenie/demo:buildcache") is True
    assert calls == [["docker", "buildx", "imagetools", "inspect",
                      "ghcr.io/asimov-agent/llgenie/demo:buildcache"]]

    # absent: probe rc 1 -> False
    def sh_miss(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1)

    monkeypatch.setattr(ei, "_sh", sh_miss)
    assert ei._cache_exists("ghcr.io/asimov-agent/llgenie/demo:buildcache") is False

    # no REGISTRY: no probe issued, always absent (local build)
    calls2: list[list[str]] = []

    def sh_noreg(cmd, **kw):
        calls2.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ei, "_sh", sh_noreg)
    monkeypatch.setattr(ei, "REGISTRY", "")
    assert ei._cache_exists("ghcr.io/asimov-agent/llgenie/demo:buildcache") is False
    assert calls2 == []


class _Resp:
    """Minimal stand-in for a `urlopen` response (the shape `_tags_list_http` uses)."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _fake_registry(monkeypatch, *, tags_responses=None, token_error=None,
                   token_payload=b'{"token": "anon-pull-token"}') -> list[str]:
    """Stub the GHCR transport `_tags_list_http` uses, and record every URL it asked.

    The seam asks two things: an anonymous pull-token exchange, then
    `GET /v2/<package>/tags/list`. `tags_responses` is consumed one entry per tags call — a
    bytes payload is the response body, an Exception is raised (an `HTTPError` for a registry
    status, a `URLError` for a transport failure). Nothing here touches the network.
    """
    seen: list[str] = []
    queue: list = list(tags_responses or [])

    def urlopen(req, timeout=None, *a, **kw):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        seen.append(url)
        if "/token" in url:
            if token_error is not None:
                raise token_error
            return _Resp(token_payload)
        item = queue.pop(0) if queue else b'{"tags": ["demo"]}'
        if isinstance(item, Exception):
            raise item
        return _Resp(item)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return seen


def _sleeps(monkeypatch) -> list[int]:
    """Capture `_package_published`'s retry backoff instead of sleeping in the suite."""
    slept: list[int] = []
    monkeypatch.setattr(ei, "time", types.SimpleNamespace(sleep=slept.append))
    return slept


def test_package_published_true_when_the_package_has_tags(monkeypatch):
    """`_package_published` is the GHCR tag-list question, and a published package answers YES.

    Contract (issue #3017): exchange an anonymous pull token for
    `repository:<package>:pull`, then `GET /v2/<package>/tags/list`. The question is about the
    PACKAGE the cache tag would live under — not about the cache tag itself.
    """

    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    seen = _fake_registry(monkeypatch, tags_responses=[b'{"tags": ["demo", "demo-buildcache"]}'])

    assert ei._package_published("ghcr.io/asimov-agent/llgenie/demo:buildcache") is True
    assert seen == [
        "https://ghcr.io/token?service=ghcr.io&scope=repository:asimov-agent/llgenie/demo:pull",
        "https://ghcr.io/v2/asimov-agent/llgenie/demo/tags/list?n=1",
    ], seen


def test_package_published_false_for_an_unpublished_package_without_retrying(monkeypatch):
    """A 404 tag list is a VERDICT about the package, not a transport failure (issue #3017).

    The unpublished case is exactly the #1880 hard `not found`: the package has no manifest, so
    `--cache-to` would fail the build. `_package_published` returns False on the FIRST 404 — the
    retries are for unreachable-registry noise, and re-asking a 404 three times per cell would
    triple the seam's registry calls for no information.
    """

    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    not_found = urllib.error.HTTPError(
        "https://ghcr.io/v2/asimov-agent/llgenie/demo/tags/list?n=1", 404, "Not Found", Message(), None)
    seen = _fake_registry(monkeypatch, tags_responses=[not_found, not_found, not_found])
    _sleeps(monkeypatch)

    assert ei._package_published("ghcr.io/asimov-agent/llgenie/demo:buildcache") is False
    assert [u for u in seen if "/tags/list" in u] == \
        ["https://ghcr.io/v2/asimov-agent/llgenie/demo/tags/list?n=1"], seen


def test_package_published_false_when_the_package_has_no_tags(monkeypatch):
    """A package whose tag list is EMPTY is treated as unpublished (fail-closed, #3017).

    A package with no tag has nothing for buildx to layer a new cache tag onto; answering
    "published" here would re-create the #1880 hard failure this change is meant to avoid.
    """

    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    _fake_registry(monkeypatch, tags_responses=[b'{"tags": []}'])

    assert ei._package_published("ghcr.io/asimov-agent/llgenie/demo:buildcache") is False


def test_package_published_retries_a_transport_failure_then_answers(monkeypatch):
    """An unreachable registry is retried with backoff, and a later answer is used (#3017).

    The measured live failure of the tag list is `URLError: <urlopen error ...>` — a Hub blip, not
    a statement about the package (the same discipline as issue #3007 for the DEAD-candidate
    probe). One retry succeeds, so the seeding decision is not lost to a blip.
    """

    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    slept = _sleeps(monkeypatch)
    seen = _fake_registry(monkeypatch, tags_responses=[
        urllib.error.URLError("connection reset"),
        b'{"tags": ["demo"]}',
    ])

    assert ei._package_published("ghcr.io/asimov-agent/llgenie/demo:buildcache") is True
    assert len([u for u in seen if "/tags/list" in u]) == 2, seen
    assert slept == [5], slept


def test_package_published_fail_closed_when_the_registry_stays_unreachable(monkeypatch):
    """After the retries the seam FAILS CLOSED: no write, build cold, cell not red (#3017).

    An unreadable registry is not evidence that the package is published; emitting `--cache-to`
    on that guess is what turns a Hub blip into the #1880 hard failure. The verdict stays
    "not published" (skip the write) and the note is printed, never a silent skip (#1796).
    """

    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    slept = _sleeps(monkeypatch)
    unreachable = urllib.error.URLError("no route to host")
    seen = _fake_registry(monkeypatch, tags_responses=[unreachable, unreachable, unreachable])

    assert ei._package_published("ghcr.io/asimov-agent/llgenie/demo:buildcache") is False
    assert len([u for u in seen if "/tags/list" in u]) == 3, seen
    assert slept == [5, 10], slept


def test_package_published_false_without_a_registry(monkeypatch):
    """No REGISTRY means no package question at all (local build, #3017)."""

    monkeypatch.setattr(ei, "REGISTRY", "")
    seen = _fake_registry(monkeypatch)

    assert ei._package_published("ghcr.io/asimov-agent/llgenie/demo:buildcache") is False
    assert seen == []


def test_cache_write_args_seeds_the_cache_when_the_package_is_published(monkeypatch, capsys):
    """Ladder state 2: absent cache ref + published package EMITS the write (issue #3017).

    This is the bug the issue was filed for. `--cache-to type=registry,ref=<missing-cache-tag>`
    only hard-fails when the ref's parent PACKAGE is absent; a published package takes the new
    `-buildcache` tag. The old code asked only the cache-ref question, which a never-seeded
    namespace answers NO forever, so it could never seed (measured: runs 44404039696 /
    44925052309 print the skip line and `asimov-agent/llgenie/edge0` has no `-buildcache` tag).
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 1)  # the cache ref itself is absent

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    seen = _package_state(monkeypatch, published=True)

    args = ei._cache_write_args("ghcr.io/asimov-agent/llgenie/demo:buildcache")

    assert args == ["--cache-to", "type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache,mode=max"], args
    assert seen == ["ghcr.io/asimov-agent/llgenie/demo:buildcache"], seen
    out = capsys.readouterr().out
    assert "seeding it (package published)" in out, out
    assert "cache write skipped" not in out, out


def test_a_push_build_seeds_a_never_seeded_cache_for_a_published_package(monkeypatch, tmp_path, capsys):
    """The publish lane seeds the namespace on its first cold build (issue #3017).

    Same shape as the #1880 tolerance test (imagetools probe rc 1) with the PACKAGE published:
    the push build gets `--cache-to` back — no `--cache-from` (nothing to read), the write in
    `mode=max`, and the seeding note printed once.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        probe = any("imagetools" in a for a in cmd)
        return subprocess.CompletedProcess(cmd, 1 if probe else 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)
    seen = _package_state(monkeypatch, published=True)

    ei._buildx("llgenie/demo:t", str(tmp_path), True, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    build = next(c for c in calls if "--push" in c)
    assert "--cache-from" not in build, build
    assert "--cache-to" in build, build
    assert "type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache,mode=max" in build, build
    # one cache-ref probe, one package question
    probes = [c for c in calls if c[:4] == ["docker", "buildx", "imagetools", "inspect"]]
    assert len(probes) == 1, probes
    assert len(seen) == 1, seen
    assert "seeding it (package published)" in capsys.readouterr().out


def test_a_privileged_local_build_seeds_a_never_seeded_cache(monkeypatch, tmp_path):
    """The CACHE_WRITE=1 owner-guarded local build seeds too (issue #3017).

    The local branch reaches the same ladder through `if CACHE_WRITE:`. Absent cache ref +
    published package -> `--cache-to mode=max` is emitted (and the read side still builds cold
    with its own single printed note).
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        if "imagetools" in cmd:  # the _cache_exists probe -> absent
            return subprocess.CompletedProcess(cmd, 1)
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)
    seen = _package_state(monkeypatch, published=True)

    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    build = calls[-1]
    assert "--cache-from" not in build, build
    assert "--cache-to" in build, build
    assert "mode=max" in " ".join(build), build
    assert len(seen) == 1, seen


def test_no_package_probe_for_a_forced_or_read_only_build(monkeypatch, tmp_path):
    """Probe budget: a build that writes nothing never asks the package question (issue #3017).

    A forced build consults neither cache side; a read-only local build (CACHE_WRITE unset) only
    reads. `_package_published` must not be called on either path — the package question exists
    only to decide a WRITE, so the sweep's normal cold reads stay one-probe builds.
    """

    def never_ask(ref: str) -> bool:
        raise AssertionError(f"no write is being decided for {ref}: the package probe must not run")

    for kwargs, label in (
        ({"force": True, "push": False}, "forced local build"),
        ({"force": False, "push": False}, "read-only local build"),
    ):
        calls: list[list[str]] = []

        def sh(cmd, **kw):
            calls.append(list(cmd))
            probe = any("imagetools" in a for a in cmd)
            return subprocess.CompletedProcess(cmd, 1 if probe else 0)

        _patch_shell(monkeypatch, sh)
        monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
        monkeypatch.setattr(ei, "CACHE_WRITE", kwargs["force"])  # forced: CACHE_WRITE on, still no write
        monkeypatch.setattr(ei, "_package_published", never_ask)

        ei._buildx("llgenie/demo:t", str(tmp_path), kwargs["push"],
                   "ghcr.io/asimov-agent/llgenie/demo:buildcache", force=kwargs["force"])

        build = calls[-1]
        assert "--cache-to" not in build, (label, build)
        assert "--cache-from" not in build, (label, build)


def test_a_present_cache_image_keeps_cache_from(monkeypatch, tmp_path):
    """A seeded registry cache is still read: the tolerance only suppresses the failure."""

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", False)

    # When an unforced build runs against an existing cache image
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then --cache-from is still emitted (unchanged layers are reused)
    build = calls[-1]
    assert any(str(a).startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache")
               and "--" not in a for a in build)
    assert "--cache-from" in build, build
    assert not any(a == "--cache-to" for a in build)  # unprivileged read stays read-only
    # and, being a read-only local build, it consults only the read side — exactly ONE probe
    probes = [c for c in calls if c[:4] == ["docker", "buildx", "imagetools", "inspect"]]
    assert len(probes) == 1, probes


def test_a_present_cache_image_still_writes_when_privileged(monkeypatch, tmp_path):
    """A seeded cache ref is still written by the privileged owner-guarded run (issue #1880).

    The write tolerance only suppresses the failure when the engine's package is absent
    from the registry. When the cache ref exists (the package is published), the
    CACHE_WRITE=1 owner-guarded build still seeds `--cache-to` for the next run — the
    write is not unconditionally dropped.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When a privileged build runs against an existing cache image
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then the cache is read AND written (the write is not dropped by the #1880 tolerance)
    build = calls[-1]
    assert "--cache-from" in build, build
    assert any(str(a).startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache,")
               and "mode=max" in str(a) for a in build)


def test_a_privileged_nonpush_build_missing_cache_writes_cold(monkeypatch, tmp_path, capsys):
    """Non-push privileged build still tolerates a missing package (issue #1880, #3017).

    The write tolerance lives on `_cache_write_args`, reached on the non-push path at
    `if CACHE_WRITE: cmd += _cache_write_args(cache_ref)`. When the engine's package is
    absent from the registry (cache probe rc 1 AND the package probe says unpublished), a
    CACHE_WRITE=1 local build must build cold and skip the cache WRITE (no `--cache-to`)
    without red — this is the verification-only owner-guarded dispatch reading a
    not-yet-published engine.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        if "imagetools" in cmd:  # the _cache_exists probe -> absent
            return subprocess.CompletedProcess(cmd, 1)
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)
    seen = _package_state(monkeypatch, published=False)

    # When a privileged non-push build runs against a missing cache ref
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then it builds cold with no --cache-from and no --cache-to (write tolerance), never red
    build = calls[-1]
    assert "--cache-from" not in build, build
    assert "--cache-to" not in build, build
    assert "--no-cache" not in build  # unforced: it is a real build but not a force rebuild
    # and the cold-read decision is printed EXACTLY once — the local branch reuses the probe
    # computed once at the top of _buildx rather than re-invoking the read helper (a fix that
    # previously double-printed the cold note on non-push builds). The package question is asked
    # once too, for the write decision only (issue #3017).
    err = capsys.readouterr()
    read_notes = [l for l in err.out.splitlines() if "cache read skipped" in l]
    assert len(read_notes) == 1, err.out
    assert len(seen) == 1, seen


def test_a_nonpush_privileged_build_probes_the_cache_once(monkeypatch, tmp_path):
    """A non-push privileged local build is also a single probe (issue #1880).

    Completes the shared-probe contract: the local branch's `_cache_read_args` and
    `_cache_write_args` also reuse the `cache_exists` computed once at the top of `_buildx`,
    so an unforced non-push build inspects the ref exactly once — not one probe per side.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When an unforced non-push privileged build runs (read + write both consult the cache)
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then exactly one imagetools inspect probe is issued, and both sides root in it
    probes = [c for c in calls if c[:4] == ["docker", "buildx", "imagetools", "inspect"]]
    assert len(probes) == 1, probes
    build = next(c for c in calls if "buildx" in c and "build" in c)
    assert "--cache-from" in build, build
    assert "--cache-to" in build, build


def test_a_forced_push_build_does_not_read_the_cache(monkeypatch, tmp_path):
    """A publishing forced build passes --no-cache and still writes the cache for later runs."""

    # Given a pushing buildx call
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When  it is forced
    ei._buildx("llgenie/demo:t", str(tmp_path), True,
               "ghcr.io/asimov-agent/llgenie/demo:buildcache", force=True)

    # Then  no layer cache is read, but the fresh layers are written back
    build = next(c for c in calls if "buildx" in c and "build" in c)
    assert "--no-cache" in build and "--push" in build
    assert not any(a == "--cache-from" for a in build)
    assert any(str(a).startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache")
               for a in build)
    # force drops the read side; only the write side consults the cache, so exactly ONE probe
    probes = [c for c in calls if c[:4] == ["docker", "buildx", "imagetools", "inspect"]]
    assert len(probes) == 1, probes


def test_a_forced_push_build_missing_cache_writes_cold(monkeypatch, tmp_path):
    """A forced PUSH build with a missing package still writes cold, never red (#1880, #3017).

    On a force push build (`force=True, push=True`), `_cache_write_args` is still
    appended to the command (the write path is not skipped by force). When the engine's
    PACKAGE is absent from the registry (`buildcache-cuda: not found`), the write
    tolerance must hold there too: no `--cache-to`, no `--cache-from` (force never reads),
    and the build proceeds — a time cost, never a red cell.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        # "imagetools inspect" is the cache-existence probe: report it absent (rc 1).
        probe = any("imagetools" in a for a in cmd)
        return subprocess.CompletedProcess(cmd, 1 if probe else 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)
    _package_state(monkeypatch, published=False)

    # When a forced PUSH build runs against a never-seeded cache whose package is unpublished
    ei._buildx("llgenie/demo:t", str(tmp_path), True,
               "ghcr.io/asimov-agent/llgenie/demo:buildcache", force=True)

    # Then the build is COLD: --no-cache, no --cache-from, no --cache-to — never red
    build = next(c for c in calls if "buildx" in c and "build" in c)
    assert "--no-cache" in build and "--push" in build
    assert "--cache-from" not in build, build
    assert "--cache-to" not in build, build


def test_a_push_build_probes_the_cache_once(monkeypatch, tmp_path):
    """A push build issues exactly ONE `imagetools inspect` probe (issue #1880).

    `_buildx` probes the cache existence once and threads the result into both
    `_cache_read_args` and `_cache_write_args`, so the same registry ref is NOT inspected
    twice per push build — one shared probe, per the refactor's contract.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When an unforced PUSH build runs (read + write both consult the cache)
    ei._buildx("llgenie/demo:t", str(tmp_path), True, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then the buildx imagetools inspect probe appears exactly once in the recorded calls,
    # and the build reads AND writes the cache (both rooted in that single probe result)
    probes = [c for c in calls if c[:4] == ["docker", "buildx", "imagetools", "inspect"]]
    assert len(probes) == 1, probes
    build = next(c for c in calls if "buildx" in c and "build" in c)
    assert "--cache-from" in build, build
    assert "--cache-to" in build, build


def test_a_forced_build_ignores_an_available_image(monkeypatch, tmp_path):
    """`available -> no rebuild` must not short-circuit a forced build."""

    # Given a tag that is already available locally or in the registry
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "_available", lambda tag: True)
    monkeypatch.setattr(ei, "build_base", lambda *a, **k: 0)
    built: list[object] = []
    monkeypatch.setattr(ei, "_buildx", lambda *a, **k: built.append(k.get("force")) or 0)

    # When  it is built with force and without
    ei.build(_spec(), force=True)
    forced = list(built)
    built.clear()
    ei.build(_spec(), force=False)

    # Then  the forced build reaches buildx, the unforced one returns before it
    assert forced == [True]
    assert built == []


def test_a_forced_build_rebuilds_the_base_stage_too(monkeypatch, tmp_path):
    """A forced engine build must not reuse the shared toolchain base (issue #638).

    Since the fix for #1753 inlines the base as an internal stage INSIDE the derived build
    (a docker-container driver cannot see a base left by a previous buildx invocation — issue
    #1753, verified on RUN 41971301136), a forced build cannot short-circuit the base: the
    `--no-cache` force reaches the ONE combined buildx invocation, which rebuilds the base
    stage AND the derived stage. Asserting `build_base` is called is no longer the contract —
    the base is not built as a separate invocation in the verify path; it is a stage in this one.
    """

    # Given the base and derived Dockerfiles exist on disk and the build records its ctx
    monkeypatch.setattr(ei, "image_exists", lambda tag: True)
    monkeypatch.setattr(ei, "REGISTRY", None)          # read-only fork/PR/verify path
    forced: list[bool] = []
    captured: dict[str, str] = {}

    def buildx(tag, ctx, push, cache_ref, force=False, **kw):
        forced.append(bool(force))
        captured["ctx_dockerfile"] = (Path(ctx) / "Dockerfile").read_text()
        return 0

    monkeypatch.setattr(ei, "_buildx", buildx)

    # When  the cell is built with force
    ei.build(_spec(), force=True)

    # Then  the ONE combined build got the force (--no-cache rebuilds the inlined base stage too)…
    assert forced == [True]
    # …and the base is a stage INSIDE the derived build, not a cross-invocation FROM base
    df = captured["ctx_dockerfile"]
    assert "AS llgenie-base" in df, df
    assert "FROM llgenie-base" in df, df
    assert "FROM llgenie/base-cpu:" not in df, df  # never re-lifts a separately-left base


def test_a_readonly_local_build_inlines_the_base_as_an_internal_stage(monkeypatch, tmp_path):
    """A non-pushing verification build must make the base resolvable on the cache-capable driver.

    Pre-#1753 the derived cell did `FROM llgenie/base-cpu:<sha>` referenced in a SEPARATE buildx
    call, which fails on the docker-container driver (base `--load`ed into the daemon is invisible
    to a later buildkit `FROM`; it falls through to docker.io and is denied — RUN 41971301136).
    The fix folds the base Dockerfile in as the first stage, rewrites the derived `FROM <base>`
    to `FROM llgenie-base`, and lifts derived in the SAME single invocation. No push rights are
    available in this cell, so a registry-qualified FROM is not an option.
    """

    monkeypatch.setattr(ei, "image_exists", lambda tag: False)
    monkeypatch.setattr(ei, "REGISTRY", None)          # read-only verify cell: no REGISTRY push
    seen: list[str] = []

    def buildx(tag, ctx, push, cache_ref, force=False, **kw):
        seen.append((Path(ctx) / "Dockerfile").read_text())
        return 0

    monkeypatch.setattr(ei, "_buildx", buildx)

    # When  a from-base cell is built read-only (the engine-build dispatch push=false path)
    ei.build(_spec(), force=False)

    # Then  the derived build lifted base+derived in one invocation, FROM points at the stage
    assert len(seen) == 1, "must be ONE buildx invocation (base is an internal stage)"
    df = seen[0]
    assert "AS llgenie-base" in df and "FROM llgenie-base" in df, df
    assert "FROM llgenie/base-cpu:" not in df, df


def test_build_engines_forwards_force_to_every_row():
    """The whole sweep can be forced: each row's make build-engine carries FORCE=1."""

    # Given the build-engines recipe
    recipe = makefiles_text(REPO).split("\nbuild-engines:", 1)[1].split("\n\n", 1)[0]

    # When  its per-row invocation is read
    # Then  FORCE is forwarded next to PUSH and VERIFY
    assert "$(if $(FORCE),FORCE=1,)" in recipe
    assert recipe.index("FORCE=1,)") < recipe.index("PUSH=1,)")


def test_a_published_image_carries_its_hash_arch_and_latest_tags(monkeypatch):
    """Every publish names the image three ways: hash tag, moving :<arch>, and :latest once per engine."""

    # Given the engine's params declare cpu/cuda/rocm/vulkan
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When  the refs of the cpu variant and of a cuda variant are read
    cpu = {"id": "llama.cpp", "tag": "llgenie/llama-cpp:23924232-3932631f-cpu", "variant": "cpu",
           "params_file": "containers/engines/params/llama.cpp.json"}
    cuda = {**cpu, "tag": "llgenie/llama-cpp:23924232-b93d412f-cuda", "variant": "cuda"}

    # Then  the hash tag and :<arch> are always there, and :latest only on the canonical variant
    assert ei.publish_refs(cpu) == [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:23924232-3932631f-cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:latest",
    ]
    assert ei.publish_refs(cuda) == [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:23924232-b93d412f-cuda",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cuda",
    ]


def test_a_gpu_only_engine_still_gets_latest(monkeypatch):
    """An engine with no cpu variant (tensorrt-llm) publishes :latest from its only variant."""

    # Given a cuda-only engine
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    spec = {"id": "tensorrt-llm", "tag": "llgenie/tensorrt-llm:c66df86d-114ad59a-cuda",
            "variant": "cuda", "params_file": "containers/engines/params/tensorrt-llm.json"}

    # When  its refs are read
    refs = ei.publish_refs(spec)

    # Then  :latest is included
    assert refs[-1] == "ghcr.io/asimov-agent/llgenie/tensorrt-llm:latest"


def test_only_one_variant_per_engine_owns_latest():
    """`:latest` must not be raced by parallel rows: exactly one variant per engine claims it."""

    # Given every engine in the committed params
    import json
    from collections import Counter

    claims = Counter()
    for path in sorted((REPO / "containers/engines/params").glob("*.json")):
        params = json.loads(path.read_text())
        owners = [v for v in params["variants"] if v == ei.engine_latest_variant(
            {"id": params["id"], "variant": v, "params_file": str(path.relative_to(REPO))})]
        claims[params["id"]] = len(owners)

    # When  the owners are counted per engine
    # Then  every engine has exactly one
    assert claims and set(claims.values()) == {1}, claims


def test_a_not_yet_published_latest_does_not_fail_the_pull_but_a_drifted_one_does(monkeypatch):
    """Rollout: `:latest` appears with the first publishing run; once it exists it must match."""

    # Given a published hash tag and :<arch> with matching digests, and no :latest yet
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    def sh(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0)

    _patch_shell(monkeypatch, sh)
    monkeypatch.setattr(ei, "publish_refs", lambda spec: [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:23924232-3932631f-cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:latest",
    ])
    digests = {"23924232-3932631f-cpu": "sha256:aa", "llama-cpp:cpu": "sha256:aa",
               "llama-cpp:latest": ""}
    monkeypatch.setattr(ei, "_digest", lambda ref: digests[next(k for k in digests if k in ref)])
    spec = _spec()

    # When  the published image is pulled
    pulled = ei.pull_published(spec)

    # Then  a missing :latest is a note, not a failure
    assert pulled == spec["tag"]

    # And   once :latest exists with another digest, the pull fails
    digests["llama-cpp:latest"] = "sha256:bb"
    assert ei.pull_published(spec) == ""


def test_a_forced_local_build_never_needs_the_container_driver(monkeypatch, tmp_path):
    """A FORCE=1 verification build exports no cache, so it must not pay the container driver's disk.

    Issue #1915: the driver gate read `not CACHE_WRITE` alone, so a FORCED local build — which
    passes neither `--cache-from` nor `--cache-to` — still ran on the docker-container builder.
    That driver's `--load` writes the image as a tar and unpacks it into dockerd on top of its
    own content store (~3x the unpacked image), and the freetoken/rocm cell died ENOSPC with
    107 GiB free (run 42326740375) after the same cell had gone green on the docker driver
    (run 41957934540). With no cache to export, the docker driver is both legal and cheap.
    """

    # Given a FORCED local build while the privileged cache-write flag is set
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When  it builds
    ei._buildx("llgenie/ft-rocm:5a73685b-a724f1d8-rocm", str(tmp_path), False,
               "ghcr.io/asimov-agent/llgenie/ft-rocm:buildcache", force=True)

    # Then  it runs on the docker driver and carries no cache flags at all
    build = calls[-1]
    assert "--builder" in build and build[build.index("--builder") + 1] == "default", build
    assert "--no-cache" in build
    assert not any(a in ("--cache-from", "--cache-to") for a in build), build


def test_a_cell_that_cannot_afford_the_export_builds_on_the_docker_driver(monkeypatch, tmp_path):
    """A cell whose image cannot fit the container driver's export+load skips the cache export.

    Issue #1915: freetoken/rocm is 16.10 GiB compressed / ~35 GiB unpacked, and the container
    driver's local path needs ~3x that on a ~107 GiB-free hosted runner. The cell must therefore
    build on the docker driver (straight into the daemon, no tar, no second copy) even on an
    unforced verification run that would otherwise export the registry cache.
    """

    # Given an UNFORCED local build of a cell listed in NO_CACHE_EXPORT
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When  it builds
    ei._buildx("llgenie/ft-rocm:5a73685b-a724f1d8-rocm", str(tmp_path), False,
               "ghcr.io/asimov-agent/llgenie/ft-rocm:buildcache", no_cache_export=True)

    # Then  the docker driver is chosen and neither cache side is touched
    build = calls[-1]
    assert "--builder" in build and build[build.index("--builder") + 1] == "default", build
    assert not any(a in ("--cache-from", "--cache-to") for a in build), build


def test_a_cell_not_in_the_map_still_exports_its_cache(monkeypatch, tmp_path):
    """The docker-driver path is per-cell: an ordinary cell keeps reading and writing the cache."""

    # Given an unforced local build of a cell that is NOT listed
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When  it builds
    ei._buildx("llgenie/llama-cpp:23924232-3932631f-cpu", str(tmp_path), False,
               "ghcr.io/asimov-agent/llgenie/llama-cpp:buildcache-cpu", no_cache_export=False)

    # Then  it stays on the container builder and both cache sides are present
    build = calls[-1]
    assert "--builder" not in build, build
    assert "--cache-from" in build and "--cache-to" in build, build


def test_the_no_cache_export_map_names_a_real_committed_cell():
    """Every NO_CACHE_EXPORT key is a committed params id x variant — no orphan, no typo."""

    import json

    # Given the committed engine params
    params_dir = REPO / "containers" / "engines" / "params"

    # When  each listed cell is looked up in its params file
    # Then  the engine ships that exact variant
    for engine, variant in ei.NO_CACHE_EXPORT:
        data = json.loads((params_dir / f"{engine}.json").read_text())
        assert variant in data["variants"], f"{engine} has no {variant} variant"
