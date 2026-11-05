"""FORCE=1 is a real rebuild (issue #638): no layer cache, no stale base, no "available, skip".

The sweep's whole purpose is to prove the pins build. A `--force` that still reads the registry
cache re-tags the previous layers instead of compiling, so the run looks green having built
nothing — which is exactly what it did before this change.
"""

from __future__ import annotations

import json
import subprocess

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import scripts.engine_image as ei  # noqa: E402
import scripts.engine_skills as es  # noqa: E402


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


def test_a_forced_push_build_does_not_read_the_cache(monkeypatch, tmp_path):
    """A publishing forced build passes --no-cache and still writes the cache for later runs."""

    # Given a pushing buildx call
    calls = _record(monkeypatch)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")

    # When  it is forced
    ei._buildx("llgenie/demo:t", str(tmp_path), True,
               "ghcr.io/asimov-agent/llgenie/demo:buildcache", force=True)

    # Then  no layer cache is read, but the fresh layers are written back
    build = calls[0]
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


def test_a_forced_build_forces_the_shared_base_too(monkeypatch, tmp_path):
    """A forced engine build must not reuse the shared toolchain base."""

    # Given the base and buildx are recorded
    monkeypatch.setattr(ei, "image_exists", lambda tag: True)
    seen: list[dict] = []

    def base(backend, force=False, push=False):
        seen.append({"backend": backend, "force": force, "push": push})
        return 0

    monkeypatch.setattr(ei, "build_base", base)
    monkeypatch.setattr(ei, "_buildx", lambda *a, **k: 0)

    # When  the cell is built with force
    ei.build(_spec(), force=True)

    # Then  build_base received force=True
    assert seen and seen[0]["force"] is True


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


def test_a_cache_write_from_build_qualifies_the_base_to_the_registry(monkeypatch, tmp_path):
    """#1753: under CACHE_WRITE the derived FROM must resolve from the registry.

    The owner-guarded engine-build dispatch stays on the docker-container builder (#1747)
    so it can export the registry cache; that driver cannot see a base `--load`-ed into
    the docker daemon, so an unqualified `FROM llgenie/base-cpu:...` falls through to
    docker.io and is denied (measured: run 41971301136 pull-access-denied). When the
    CACHE_WRITE build is the base for a FROM, it must PUSH the base to the registry and
    qualify the FROM accordingly. Fork/PR/local builds (CACHE_WRITE unset) use the
    docker-driver `default` builder which sees the locally-loaded base, so they keep the
    bare FROM exactly as before.
    """
    import scripts.engine_image as ei  # noqa: F811

    # A repo tree whose Dockerfile.cpu has the unpinned `FROM llgenie/base-cpu:<pin>`.
    root = tmp_path / "repo"
    dfile = root / "containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu"
    dfile.parent.mkdir(parents=True)
    base = es.base_tag("cpu")
    dfile.write_text(f"FROM {base}\nRUN echo base\n")
    params = root / "containers/engines/params/llama.cpp.json"
    params.parent.mkdir(parents=True)
    params.write_text(json.dumps({"engine": "llama.cpp", "variants": {"cpu": {}},
                                  "pinned": "p", "repo": "r"}))

    spec = {"id": "llama.cpp", "tag": "llgenie/llama-cpp:test-cpu", "variant": "cpu",
            "backend": "cpu", "dockerfile": "containers/engines/dockerfiles/llama.cpp/Dockerfile.cpu",
            "params_file": "containers/engines/params/llama.cpp.json"}
    monkeypatch.setattr(es, "REPO_ROOT", root)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "_available", lambda tag: False)  # force a build every time

    def _run(cache_write: bool) -> tuple[list[list[str]], str]:
        calls: list[list[str]] = []
        def sh(cmd, **kw):
            calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0)
        monkeypatch.setattr(ei, "_sh", sh)
        monkeypatch.setattr(ei, "CACHE_WRITE", cache_write)
        assert ei.build(spec) == 0
        # the derived buildx `_sh(cmd + [ctx])` last arg is the ctx dir; read its Dockerfile
        ctx = calls[-1][-1]
        return calls, (Path(ctx) / "Dockerfile").read_text()

    # When CACHE_WRITE is set (owner dispatch stays on the container builder)
    calls, dockerfile = _run(True)
    # Then the base was pushed to the registry (--push + qualified tag)
    pushed = any("--push" in c and any("ghcr.io/asimov-agent/llgenie/base-cpu:" in a for a in c) for c in calls)
    assert pushed, calls
    # And the derived FROM is qualified to the registry, not a bare docker.io ref
    assert f"FROM ghcr.io/asimov-agent/{base}" in dockerfile, dockerfile
    assert f"FROM {base}" not in dockerfile, dockerfile

    # When CACHE_WRITE is unset (fork/PR/local build on the docker-driver `default` builder)
    calls, dockerfile = _run(False)
    # Then no push happened and the bare FROM is kept (locally-loaded base is visible)
    assert not any("--push" in c for c in calls)
    assert f"FROM {base}" in dockerfile, dockerfile
