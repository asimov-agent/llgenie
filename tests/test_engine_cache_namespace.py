"""Issue #2891: the buildx registry layer-cache refs track the content hashes the
image tags already carry (OpenSpec change engine-cache-namespace-2891).

The seam used fixed cache namespaces (`llgenie/base-<backend>:buildcache`,
`llgenie/<engine>:buildcache-<variant>`): a base bump replayed against a stale,
content-unrelated namespace. These tests pin the content-keyed derivations
hermetically — no docker, no network: the `buildx` seam is stubbed and the
registry cache ref it was handed is asserted, for base and cell, before and
after a content change.
"""
from __future__ import annotations

import json
from pathlib import Path

import scripts.engine_image as ei
import scripts.engine_skills as es


def _point(monkeypatch, repo: Path):
    """Same dual-import pointing the matrix tests use: `engine_image` imports the
    skills module under its bare name, so patch the object `ei` actually binds."""
    monkeypatch.setattr(es, "REPO_ROOT", repo)
    monkeypatch.setattr(es, "CONTAINER_DIR", repo / "containers" / "engines")
    monkeypatch.setattr(es, "BASE_DIR", repo / "containers" / "engines" / "base")
    monkeypatch.setattr(ei, "es", es)
    monkeypatch.setattr(ei, "REGISTRY", "ghcr.io/asimov-agent")
    monkeypatch.setattr(ei, "_available", lambda tag: False)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "containers" / "engines" / "base").mkdir(parents=True)
    (repo / "containers" / "engines" / "dockerfiles" / "vllm").mkdir(parents=True)
    (repo / "containers" / "engines" / "params").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    for p, body in {
        "containers/engines/entrypoint.sh": "#!/bin/sh\n",
        "scripts/engine_runner.py": "# runner\n",
        "containers/engines/base/Dockerfile.cuda": "FROM nvidia/cuda:13.0.2-devel-ubuntu24.04\n",
        "containers/engines/base/Dockerfile.cpu": "FROM ubuntu:24.04\n",
    }.items():
        (repo / p).write_text(body)
    return repo


def _params(pinned: str) -> str:
    return json.dumps({
        "id": "vllm", "engine": "vllm-project/vllm", "repo": "vllm-project/vllm",
        "pinned": pinned,
        "variants": {"cuda": {"backend": "cuda", "image": "ubuntu", "build": ["echo"],
                               "apt": [], "build_args": {}, "run_args": [], "port": 8000,
                               "base": es.base_tag("cuda")}},
    })


def _cell_spec(repo: Path, tag: str) -> dict:
    return {"id": "vllm", "engine": "vllm-project/vllm", "backend": "cuda",
            "variant": "cuda", "tag": tag,
            "dockerfile": "containers/engines/dockerfiles/vllm/Dockerfile.cuda",
            "params_file": "containers/engines/params/vllm.json"}


def _stub_buildx(monkeypatch) -> dict:
    captured: dict = {}

    def fake_buildx(tag, ctx, push, cache_ref, force=False, **kw):
        captured["tag"] = tag
        captured["cache_ref"] = cache_ref
        return 0

    monkeypatch.setattr(ei, "_buildx", fake_buildx)
    return captured


def test_base_cache_ref_carries_the_base_content_hash(tmp_path, monkeypatch):
    """AC 3 (base half): the base cache ref IS the base tag + `-buildcache` — the
    rendered base Dockerfile's digest, not a fixed `:buildcache` name."""
    _point(monkeypatch, _repo(tmp_path))
    captured = _stub_buildx(monkeypatch)
    assert ei.build_base("cuda", push=True) == 0
    base_tag = es.base_tag("cuda")  # llgenie/base-cuda:<sha256(render_base_dockerfile)[:10]>
    assert captured["tag"] == base_tag
    assert captured["cache_ref"] == f"ghcr.io/asimov-agent/{base_tag}-buildcache"
    assert base_tag.split(":")[1] in captured["cache_ref"]


def test_changed_base_content_starts_a_new_base_cache_namespace(tmp_path, monkeypatch):
    """AC 3: bump the base's *content* (here: an added line in the rendered
    Dockerfile) and the cache namespace changes with it — no stale replay."""
    repo = _repo(tmp_path)
    _point(monkeypatch, repo)
    captured = _stub_buildx(monkeypatch)
    assert ei.build_base("cuda", push=True) == 0
    before = captured["cache_ref"]

    real = es.render_base_dockerfile
    monkeypatch.setattr(es, "render_base_dockerfile",
                        lambda backend: real(backend) + "# package bump\n")
    assert ei.build_base("cuda", push=True) == 0
    after = captured["cache_ref"]

    assert after != before
    assert after == f"ghcr.io/asimov-agent/{es.base_tag('cuda')}-buildcache"
    assert es.base_tag("cuda").split(":")[1] not in before


def test_unchanged_content_replays_the_same_cache_namespace(tmp_path, monkeypatch):
    """AC 2's precondition: the same rendered content must yield the SAME namespace,
    or a warm replay would read a different cache than the one that was exported."""
    repo = _repo(tmp_path)
    _point(monkeypatch, repo)
    captured = _stub_buildx(monkeypatch)
    assert ei.build_base("cpu", push=True) == 0
    first = captured["cache_ref"]
    assert ei.build_base("cpu", push=True) == 0
    assert captured["cache_ref"] == first


def test_cell_cache_ref_carries_the_full_tag_suffix(tmp_path, monkeypatch):
    """The cell cache ref is the cell's full tag (`<pin8>-<content-hash>-<variant>`)
    plus `-buildcache`: variant AND both hash segments, keyed to content."""
    repo = _repo(tmp_path)
    _point(monkeypatch, repo)
    tag = f"llgenie/vllm:{'abcd1234'[:8]}-ef567890-cuda"
    (repo / "containers/engines/params/vllm.json").write_text(_params("abcd1234deadbeef"))
    (repo / "containers/engines/dockerfiles/vllm/Dockerfile.cuda").write_text(
        f"FROM {es.base_tag('cuda')}\nRUN echo build\n")
    captured = _stub_buildx(monkeypatch)
    assert ei.build(_cell_spec(repo, tag), push=True) == 0
    assert captured["cache_ref"] == f"ghcr.io/asimov-agent/{tag}-buildcache"


def test_cell_cache_namespace_changes_when_the_tag_hash_changes(tmp_path, monkeypatch):
    """A base or cell content change lands as a new tag hash — the cache namespace
    follows it, which is exactly the issue's `539dc9d6-e82c9353` pin shape."""
    repo = _repo(tmp_path)
    _point(monkeypatch, repo)
    (repo / "containers/engines/params/vllm.json").write_text(_params("abcd1234deadbeef"))
    (repo / "containers/engines/dockerfiles/vllm/Dockerfile.cuda").write_text(
        f"FROM {es.base_tag('cuda')}\nRUN echo build\n")
    captured = _stub_buildx(monkeypatch)

    assert ei.build(_cell_spec(repo, "llgenie/vllm:abcd1234-ef567890-cuda"), push=True) == 0
    before = captured["cache_ref"]
    assert ei.build(_cell_spec(repo, "llgenie/vllm:abcd1234-99ff00aa-cuda"), push=True) == 0
    after = captured["cache_ref"]

    assert before != after
    assert after == "ghcr.io/asimov-agent/llgenie/vllm:abcd1234-99ff00aa-cuda-buildcache"
