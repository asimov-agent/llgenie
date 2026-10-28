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
    return {"id": "llama.cpp", "tag": "llgenie/llama-cpp:39febd2a-3932631f-cpu", "variant": "cpu",
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

    # Then  --cache-from is there and --no-cache is not
    build = calls[-1]
    assert "--no-cache" not in build
    assert "type=registry,ref=ghcr.io/asimov-agent/llgenie/demo:buildcache" in build


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
    cpu = {"id": "llama.cpp", "tag": "llgenie/llama-cpp:39febd2a-3932631f-cpu", "variant": "cpu",
           "params_file": "containers/engines/params/llama.cpp.json"}
    cuda = {**cpu, "tag": "llgenie/llama-cpp:39febd2a-b93d412f-cuda", "variant": "cuda"}

    # Then  the hash tag and :<arch> are always there, and :latest only on the canonical variant
    assert ei.publish_refs(cpu) == [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:39febd2a-3932631f-cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:latest",
    ]
    assert ei.publish_refs(cuda) == [
        "ghcr.io/asimov-agent/llgenie/llama-cpp:39febd2a-b93d412f-cuda",
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
        "ghcr.io/asimov-agent/llgenie/llama-cpp:39febd2a-3932631f-cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:cpu",
        "ghcr.io/asimov-agent/llgenie/llama-cpp:latest",
    ])
    digests = {"39febd2a-3932631f-cpu": "sha256:aa", "llama-cpp:cpu": "sha256:aa",
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
