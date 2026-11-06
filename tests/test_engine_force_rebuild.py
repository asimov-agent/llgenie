"""FORCE=1 is a real rebuild (issue #638): no layer cache, no stale base, no "available, skip".

The sweep's whole purpose is to prove the pins build. A `--force` that still reads the registry
cache re-tags the previous layers instead of compiling, so the run looks green having built
nothing — which is exactly what it did before this change.
"""

from __future__ import annotations

import subprocess

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import scripts.engine_image as ei  # noqa: E402


def _spec() -> dict:
    return {"id": "llama.cpp", "tag": "llgenie/llama-cpp:1b6935b2-3932631f-cpu", "variant": "cpu",
            "backend": "cpu", "dockerfile": "containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu",
            "params_file": "containers/engines/params/llama.cpp.json"}


def _record(monkeypatch, rc: int = 0) -> list[list[str]]:
    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, rc)

    monkeypatch.setattr(ei, "_sh", sh)
    return calls


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
    """A never-seeded registry cache must not red the cell (issues #1842, #1880).

    `--cache-from type=registry,ref=<missing>` makes buildx fail the whole build with
    `manifest unknown`, and `--cache-to type=registry,ref=<missing-package>` fails with
    `not found` when the engine's package is not on the registry yet. The read AND the
    write must tolerate the absence: when the probe finds no cache image the build
    proceeds cold (no --cache-from, no --cache-to) — a time cost, never a red cell.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        # "imagetools inspect" is the cache-existence probe: report it absent (rc 1).
        # Every other command (including the build itself) succeeds.
        probe = any("imagetools" in a for a in cmd)
        return subprocess.CompletedProcess(cmd, 1 if probe else 0)

    monkeypatch.setattr(ei, "_sh", sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When an unforced build runs against a never-seeded cache
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then the build is COLD: no --cache-from and no --cache-to (no manifest-unknown /
    # not-found failure) — a missing cache is a time cost, never a red cell
    build = calls[-1]
    assert "--cache-from" not in build, build
    assert "--cache-to" not in build, build


def test_push_build_missing_cache_image_builds_cold_not_red(monkeypatch, tmp_path):
    """A never-seeded cache must not red a PUSH build either (issue #1880).

    The AC1 failing cell (`engine-build-tensorfold-cuda` in the default sweep, run
    `42280478755`) is a PUSH build: `_buildx(..., push=True)` runs the
    `if push and REGISTRY:` branch that appends `_cache_write_args`. The write-side
    tolerance must hold there too — when the engine's package is absent from the
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

    monkeypatch.setattr(ei, "_sh", sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When an unforced PUSH build runs against a never-seeded cache
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

    monkeypatch.setattr(ei, "_sh", sh)
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
    """`_cache_write_args` returns [] when the engine's package is absent (issue #1880).

    The write-side tolerance is the whole point of #1881: a `--cache-to
    type=registry,ref=<missing-package>` fails the WHOLE build with `not found` when
    the engine's package is not on the registry yet. Direct unit test of the function
    (the push-path tests exercise it through `_buildx`; this pins the contract).
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        # "imagetools inspect" is the cache-existence probe: report it absent (rc 1).
        return subprocess.CompletedProcess(cmd, 1)

    monkeypatch.setattr(ei, "_sh", sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When the engine's package is absent from the registry
    args = ei._cache_write_args("ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then no --cache-to is emitted (a cold build, never a red cell)
    assert args == [], args


def test_cache_write_args_emits_cache_to_when_present(monkeypatch):
    """`_cache_write_args` emits --cache-to when the cache ref exists (issue #1880).

    The tolerance only suppresses the failure when the package is absent; a present
    cache ref must still be written (mode=max) for the next run.
    """

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ei, "_sh", sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When the engine's package IS on the registry
    args = ei._cache_write_args("ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then --cache-to is emitted with mode=max (the write still seeds the cache)
    assert args == ["--cache-to", "type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache,mode=max"], args


def test_cache_write_args_empty_without_registry(monkeypatch):
    """`_cache_write_args` returns [] when REGISTRY is unset (local build)."""

    monkeypatch.setattr(ei, "REGISTRY", "")

    assert ei._cache_write_args("ghcr.io/asimov-agent/llgenie/demo:buildcache") == []


def test_a_present_cache_image_keeps_cache_from(monkeypatch, tmp_path):
    """A seeded registry cache is still read: the tolerance only suppresses the failure."""

    calls: list[list[str]] = []

    def sh(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ei, "_sh", sh)
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

    monkeypatch.setattr(ei, "_sh", sh)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "CACHE_WRITE", True)

    # When a privileged build runs against an existing cache image
    ei._buildx("llgenie/demo:t", str(tmp_path), False, "ghcr.io/asimov-agent/llgenie/demo:buildcache")

    # Then the cache is read AND written (the write is not dropped by the #1880 tolerance)
    build = calls[-1]
    assert "--cache-from" in build, build
    assert any(str(a).startswith("type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache,")
               and "mode=max" in str(a) for a in build)


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

    def buildx(tag, ctx, push, cache_ref, force=False):
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

    def buildx(tag, ctx, push, cache_ref, force=False):
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
    recipe = (REPO / "Makefile").read_text().split("\nbuild-engines:", 1)[1].split("\n\n", 1)[0]

    # When  its per-row invocation is read
    # Then  FORCE is forwarded next to PUSH and VERIFY
    assert "$(if $(FORCE),FORCE=1,)" in recipe
    assert recipe.index("FORCE=1,)") < recipe.index("PUSH=1,)")


def test_a_published_image_carries_its_hash_arch_and_latest_tags(monkeypatch):
    """Every publish names the image three ways: hash tag, moving :<arch>, and :latest once per engine."""

    # Given the engine's params declare cpu/cuda/rocm/vulkan
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When  the refs of the cpu variant and of a cuda variant are read
    cpu = {"id": "llama.cpp", "tag": "llgenie/llama-cpp:1b6935b2-3932631f-cpu", "variant": "cpu",
           "params_file": "containers/engines/params/llama.cpp.json"}
    cuda = {**cpu, "tag": "llgenie/llama-cpp:1b6935b2-b93d412f-cuda", "variant": "cuda"}

    # Then  the hash tag and :<arch> are always there, and :latest only on the canonical variant
    assert ei.publish_refs(cpu) == [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:1b6935b2-3932631f-cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:latest",
    ]
    assert ei.publish_refs(cuda) == [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:1b6935b2-b93d412f-cuda",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cuda",
    ]


def test_a_gpu_only_engine_still_gets_latest(monkeypatch):
    """An engine with no cpu variant (tensorrt-llm) publishes :latest from its only variant."""

    # Given a cuda-only engine
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    spec = {"id": "tensorrt-llm", "tag": "llgenie/tensorrt-llm:376f7e1b-114ad59a-cuda",
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

    monkeypatch.setattr(ei, "_sh", sh)
    monkeypatch.setattr(ei, "publish_refs", lambda spec: [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:1b6935b2-3932631f-cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:latest",
    ])
    digests = {"1b6935b2-3932631f-cpu": "sha256:aa", "llama-cpp:cpu": "sha256:aa",
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
