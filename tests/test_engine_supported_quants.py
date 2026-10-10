"""llgenie per-engine supported-quant range (OpenSpec feat-pick-vram-ram-matrix-tests,
issue #122): the business rule behind the interactive pick —

    pick a model -> its supported engines (by VRAM/RAM/arch)
    -> for the engine you selected, the RANGE of quants THAT engine supports
    -> the HIGHEST quant that fits your (VRAM, RAM) spec
                       (unless you name a specific file)

`model_engine_pick.engine_supported_quants` returns that range (ascending size, each a
real resolvable download plan); `pick_quant` returns its last element (the highest that
fits). These are the same functions the matrix and the interactive pick use.

Unit + live assertions: hermetic logic checks (pure, no network) for the ordering,
size-fit and highest-pick contract, plus LIVE checks that every supported quant is a
real, downloadable HF link. Nominal (24 GB / 64 GB cuda) host is stubbed via the env
seams; the engine is never started — only its quant range and chosen download are
examined (no model download, only link-existence probes).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

REGISTRY = REPO / "data" / "models.json"
CATALOG = REPO / "data" / "trending-quant-catalog.json"
GB = 2**30

ARCHES = ("cuda", "rocm", "vulkan", "cpu", "metal")


def _stub_host(vram=24, ram=64, arch="cuda"):
    """Stub the host the CI way (env seams), so engine_supported_quants/pick_quant run
    through the real card_gb/system_ram_gb/host_arch detection path."""
    os.environ["LLAMA_RAM_BYTES"] = str(int(vram * GB))
    os.environ["LLGENIE_SYSTEM_RAM_BYTES"] = str(int(ram * GB))
    os.environ["LLAMA_BACKEND"] = arch


def test_supported_quants_are_ascending_and_fit_budget():
    # Given a real model + engine and a 24 GB / 64 GB cuda host (env-stubbed)
    _stub_host(24, 64, "cuda")
    m = next(x for x in mp.load_registry(str(REGISTRY))["models"] if x["id"] == "qwen3.8-27b")
    eng, = (e for e in mp.rank_engines(m, "cuda") if e["id"] == "llama.cpp")
    budget = mp.weight_budget_gb(24, mp.is_moe(m), 64, "cuda") * GB
    # When the engine's supported quant range is computed
    qs = mp.engine_supported_quants(m, eng, 24, 64, "cuda")
    # Then it is ascending by size, every entry fits the budget, and each is a real
    # resolvable plan
    assert qs and [q["size"] for q in qs] == sorted(q["size"] for q in qs)
    assert all(q["size"] <= budget for q in qs)
    assert all(q.get("repo") and q.get("files") for q in qs)
    # and the pick is the last (highest) one
    assert mp.pick_quant(m, eng, 24, 64, "cuda") == qs[-1]
    assert qs[-1]["size"] == max(q["size"] for q in qs)


def test_supported_quants_narrow_to_the_engines_own_format():
    # Given a model served by engines of DIFFERENT formats (LLM cached GGUF + MLX)
    _stub_host(24, 64, "cuda")
    m = next(x for x in mp.load_registry(str(REGISTRY))["models"] if x["id"] == "qwen3.8-27b")
    # When each engine's supported range is computed (one gguf-reader, one mlx-reader)
    gguf_qs = mp.engine_supported_quants(
        m, next(e for e in mp.rank_engines(m, "cuda") if e["id"] == "llama.cpp"), 24, 64, "cuda")
    mlx_qs = mp.engine_supported_quants(
        m, next(e for e in mp.rank_engines(m, "cuda") if e["id"] == "mlx"), 24, 64, "cuda")
    # Then each range only offers quants of the format THAT engine reads
    assert gguf_qs and all(any(f.endswith(".gguf") for f in q["files"]) for q in gguf_qs)
    assert mlx_qs and all(q.get("dir") for q in mlx_qs)  # whole-repo MLX snapshot
    assert qs_repos(gguf_qs) != qs_repos(mlx_qs)


def qs_repos(qs):
    return {q["repo"] for q in qs}


@pytest.mark.parametrize("arch", ARCHES)
@pytest.mark.parametrize("model_id", [m["id"] for m in mp.load_registry(str(REGISTRY))["models"]])
def test_pick_is_a_real_catalog_link(model_id, arch):
    """For every real (model x engine x arch), the engine's chosen quant (pick_quant —
    the highest that fits) must be a real link in the committed trending-quant catalog.
    (HTTP-200 existence is covered by the bounded catalog probe and the full-registry
    suite, so this stays fast: no per-quant network probe here.)"""
    import json

    _stub_host(24, 64, arch)
    catalog = set()
    for cell in (json.loads(CATALOG.read_text())["files"] or {}).get(model_id, {}).values():
        for it in cell["quants"]:
            rev = it.get("revision", "main")
            for f in (it.get("files") or [it["path"]]):
                catalog.add(f"https://huggingface.co/{it['repo']}/resolve/{rev}/{f}")
    m = next(x for x in mp.load_registry(str(REGISTRY))["models"] if x["id"] == model_id)
    row = next((r for r in mp.matrix({"models": [m]}, 24, 64, arch)["permutations"]
                if r["model"]["id"] == model_id), None)
    if row is None:
        return  # not offered on this arch
    for cell in row["engines"]:
        eng = cell["engine"]  # the engine dict (matrix wraps it in the cell)
        picked = mp.pick_quant(m, eng, 24, 64, arch)
        # the engine's chosen download must be one of the catalog's real quant links
        assert picked, f"{model_id}/{eng['id']} on {arch}: pickable engine has no quant"
        for u in mp.plan_url(picked):
            assert u in catalog, \
                f"{model_id}/{eng['id']} on {arch}: {u} not in the quant catalog"
