"""llgenie VRAM/RAM model x engine x quant permutation matrix (OpenSpec
feat-pick-vram-ram-matrix-tests, issue #122).

Hermetic unit tests: a synthetic registry + stubbed Hub tree (deterministic GGUF
sizes) + stubbed engine registry, so VRAM and RAM are mocked and the exact HF
URL of every runnable choice is asserted with no network.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

GB = 2**30

# -- a synthetic registry with the shapes matrix() consumes --------------------
def _model(id_, name, vram, hf_repo, tps, hw, type_="LLM", supported=None, last="2026-10-09"):
    return {
        "id": id_, "name": name, "type": type_, "params": name.split()[0],
        "hf": hf_repo, "vram_tier": vram,
        "formats": [{"name": "GGUF", "hf": hf_repo}],
        "engines": [{"engine": "llama.cpp" if supported is not None else "llama.cpp",
                     "tps": str(tps), "hardware": hw}],
        "supported_engines": supported or ["llama.cpp"],
        "last_seen": last, "engagement": {"trend_score": 1.0, "posts_7d": 1},
    }


def _mkreg():
    models = [
        # one MoE, in README-first position so it is the top row when it fits
        _model("qwen3.8-27b", "Qwen3.8-27B", "16GB", "Qwen/Qwen3.8-27B-GGUF",
               100, "RTX 3090 24GB", type_="LLM (MoE)", supported=["llama.cpp", "vllm"]),
        _model("qwen3-8b", "Qwen3 8B", "8GB", "Qwen/Qwen3-8B-GGUF",
               150, "RTX 4090", supported=["llama.cpp", "vllm"]),
        # smallest GGUF (20 GB) exceeds the 16 GB VRAM budget -> skip with why
        _model("big-16b", "Big 16B", "16GB", "FakeOrg/Big-16B-GGUF", 60, "RTX 4090"),
        # vram_tier above the small cards -> excluded from them entirely
        _model("huge-48b", "Huge 48B", "48GB", "FakeOrg/Huge-48B-GGUF", 40, "RTX 4090"),
        # a Strata-only model -> its engine gets Strata's own plan, never a generic GGUF
        _model("flash-next", "Flash Next 125B", "12GB", "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF",
               80, "RTX 4090", type_="LLM (MoE)", supported=["Strata"]),
    ]
    models[0]["engines"][0]["engine"], models[1]["engines"][0]["engine"] = "llama.cpp", "vllm"
    models[4]["engines"][0]["engine"] = "Strata"
    return {"generated_utc": "2026-10-10T00:00:00Z", "models": models}


# -- a stubbed Hub tree: exact, deterministic sizes per repo -------------------
def _f(path, size):
    return {"path": path, "type": "file", "size": size}


def _trees():
    return {
        "Qwen/Qwen3.8-27B-GGUF": [
            _f("Qwen3.8-27B-Q8_0.gguf", 27 * GB),
            _f("Qwen3.8-27B-Q5_K_M.gguf", 18 * GB),
            _f("Qwen3.8-27B-Q4_K_M.gguf", 13 * GB),
            _f("Qwen3.8-27B-Q3_K_M.gguf", 9 * GB),
        ],
        "Qwen/Qwen3-8B-GGUF": [
            _f("Qwen3-8B-Q8_0.gguf", int(8.5 * GB)),
            _f("Qwen3-8B-Q5_K_M.gguf", int(5.6 * GB)),
            _f("Qwen3-8B-Q4_K_M.gguf", int(4.8 * GB)),
        ],
        "FakeOrg/Big-16B-GGUF": [_f("Big-16B-Q8_0.gguf", 20 * GB)],
        "FakeOrg/Huge-48B-GGUF": [_f("Huge-48B-Q4_K_M.gguf", 40 * GB)],
    }


IDS = {
    "llama.cpp": {"id": "llama-cpp", "formats": ["gguf"], "variants": ["cuda", "cpu"]},
    "vllm": {"id": "vllm", "formats": ["gguf", "safetensors"], "variants": ["cuda", "cpu"]},
    "Strata": {"id": "strata", "formats": ["gguf"], "variants": ["cuda", "cpu"]},
}


@pytest.fixture(autouse=True)
def _no_catalog(monkeypatch):
    """These hermetic matrix tests stub the Hub tree (deterministic sizes) and
    assert exact URLs via the LIVE-resolving path — disable the committed quant
    catalog so it does not override the stubbed tree. The catalog's own path is
    asserted by test_engine_supported_quants and the full-registry system test."""
    monkeypatch.setenv("LLGENIE_QUANT_CATALOG", "0")


@pytest.fixture()
def matrix_env(monkeypatch):
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": _trees().get(repo, []))
    monkeypatch.setattr(mp, "engine_ids", lambda: IDS)
    return mp.matrix(_mkreg(), 16, 32, "cuda")


# -- spec scenario: a concrete HF URL for a representative vram/ram key ---------
def test_matrix_top_row_url_fits_vram_and_ram(matrix_env):
    # Given a 16 GB / 32 GB cuda host and a MoE model whose repo carries several quants
    res = matrix_env

    # When the matrix is computed
    # Then the top (README-first) row is the MoE model, the plan is the largest
    # quant within the MoE budget (VRAM 11.8 + RAM 28 = 39.8), and its URL is exact
    top = res["permutations"][0]
    assert top["model"]["id"] == "qwen3.8-27b"
    cell = top["engines"][0]
    assert cell["engine"]["id"] == "llama-cpp"
    assert cell["url"] == ["https://huggingface.co/Qwen/Qwen3.8-27B-GGUF/resolve/main/"
                           "Qwen3.8-27B-Q8_0.gguf"]

    # the largest-quant-that-fits invariant holds for every permutation
    budget = mp.weight_budget_gb(16, True, 32, "cuda") * GB
    assert 27 * GB <= budget  # the chosen Q8_0 fits the MoE budget
    for row in res["permutations"]:
        m = row["model"]  # noqa: F841
        for c in row["engines"]:
            assert c["plan"]["size"] <= budget
            assert c["plan"]["size"] == max(
                w["size"] for w in mp.gguf_weights(c["plan"]["repo"]) if w["size"] <= budget)


# -- spec scenario: no row when the vram tier exceeds the card -----------------
def test_matrix_excludes_models_over_vram(monkeypatch):
    # Given models of 8 GB, 16 GB and 48 GB vram_tier
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": _trees().get(repo, []))
    monkeypatch.setattr(mp, "engine_ids", lambda: IDS)

    # When the matrix is computed for an 8 GB card
    res = mp.matrix(_mkreg(), 8, 32, "cuda")
    ids = {r["model"]["id"] for r in res["permutations"]}

    # Then nothing above 8 GB is offerable (in a permutation or a skip-with-why),
    # and the 8 GB model is
    assert "qwen3-8b" in ids
    assert "qwen3.8-27b" not in ids and "huge-48b" not in ids and "big-16b" not in ids
    assert all(s["model"] not in ("huge-48b",) for s in res["skipped"])


# -- spec scenario: a moe model binds ram on a tight-ram gpu host --------------
def test_matrix_binds_moe_quant_to_ram(monkeypatch):
    # Given a MoE model on a fixed 16 GB card
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": _trees().get(repo, []))
    monkeypatch.setattr(mp, "engine_ids", lambda: IDS)

    # When RAM is generous (32 GB) versus tight (4 GB)
    roomy = mp.matrix(_mkreg(), 16, 32, "cuda")
    tight = mp.matrix(_mkreg(), 16, 4, "cuda")
    url = lambda r: r["permutations"][0]["engines"][0]["url"][0]  # noqa: E731

    # Then RAM drops the largest quants: 32 GB RAM holds the Q8_0 (MoE budget
    # 11.8+28=39.8), 4 GB RAM only a quant within 11.8 GB (the Q3_K_M)
    assert url(roomy) == "https://huggingface.co/Qwen/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-Q8_0.gguf"
    assert url(tight) == "https://huggingface.co/Qwen/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-Q3_K_M.gguf"
    assert url(roomy) != url(tight)


# -- spec scenario: strata gets its own sharded plan ---------------------------
def test_matrix_engine_specific_plan_strata(monkeypatch):
    # Given a Strata-only model and a shared Strata plan
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": _trees().get(repo, []))
    monkeypatch.setattr(mp, "engine_ids", lambda: IDS)
    fixed = {"repo": "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF", "revision": "abc123",
             "path": "Qwen3.8-Flash-Next-IQ3_XXS/model.gguf",
             "files": ["Qwen3.8-Flash-Next-IQ3_XXS/model.gguf"], "size": 7 * GB,
             "strata": {"family": "Qwen3.8-Flash-Next", "model": "IQ3_XXS"}}
    monkeypatch.setattr(mp, "strata_serves", lambda m: True)
    monkeypatch.setattr(mp, "strata_plan", lambda ram: fixed)

    # When the matrix selects the Strata engine
    res = mp.matrix(_mkreg(), 16, 32, "cuda")
    row = next(r for r in res["permutations"] if r["model"]["id"] == "flash-next")

    # Then it is Strata's own pinned-revision file, never a generic GGUF
    cell = row["engines"][0]
    assert cell["engine"]["id"] == "strata" and cell["use_format"] == "gguf"
    assert cell["url"] == ["https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/"
                           "resolve/abc123/Qwen3.8-Flash-Next-IQ3_XXS/model.gguf"]


# -- spec scenario: the matrix scales with vram ---------------------------------
def test_matrix_scales_with_vram(monkeypatch):
    # Given a registry spanning 8/16/48 GB cards
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": _trees().get(repo, []))
    monkeypatch.setattr(mp, "engine_ids", lambda: IDS)

    # When VRAM is raised from 8 to 48 GB, and a dense model's quant is looked up by id
    tiny = mp.matrix(_mkreg(), 8, 32, "cuda")
    big = mp.matrix(_mkreg(), 48, 32, "cuda")
    s8 = {r["model"]["id"] for r in tiny["permutations"]}
    b48 = {r["model"]["id"] for r in big["permutations"]}

    # Then 48 GB offers a strict superset and, for the dense qwen3-8b, a LARGER quant
    assert s8 <= b48 and "qwen3-8b" in b48
    size_of = lambda res, i: next(r["engines"][0]["plan"]["size"]  # noqa: E731
                                   for r in res["permutations"] if r["model"]["id"] == i)
    assert size_of(tiny, "qwen3-8b") == int(4.8 * GB)   # 8 GB VRAM -> Q4_K_M
    assert size_of(big, "qwen3-8b") == int(8.5 * GB)    # 48 GB VRAM -> Q8_0
    assert size_of(big, "qwen3-8b") > size_of(tiny, "qwen3-8b")


# -- spec scenario: llgenie --matrix prints rows and exits 0 --------------------
def test_llgenie_matrix_prints_urls(tmp_path):
    """The CLI prints every permutation's HF URL and exits 0 on non-tty stdin
    (the smoke registry points at the real, small health-check GGUF repo)."""
    smoke = REPO / "tests" / "fixtures" / "matrix-smoke-registry.json"
    env = {**os.environ, "LLGENIE_REGISTRY_SRC": str(smoke),
           "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": "cpu"}
    # Given --matrix 24 32 on stdin that is not a tty
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llama_serve.py"),
                        "--matrix", "24", "32"],
                       capture_output=True, text=True, env=env, timeout=120,
                       input="")
    # Then it exits 0 and prints the resolvable Hub URL of its one permutation
    assert r.returncode == 0, r.stderr
    assert "huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/" in r.stdout
    assert "no download, no serve" in r.stdout
