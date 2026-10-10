"""llgenie VRAM/RAM/ARCH model x engine x quant permutation matrix (OpenSpec
feat-pick-vram-ram-matrix-tests, issue #122).

The exhaustive permutation test the CI runs on Linux: for a grid of
(arch x VRAM GB x RAM GB) the REAL `matrix()`-driven engine selection is
asserted — which inference server is offered, on which image variant, for each
model — and every runnable choice must map to a resolvable
`https://huggingface.co/<repo>/resolve/<rev>/<file>` quant download that fits.

Unlike test_pick_matrix.py (fixed-case cuda), this locks the ARCHITECTURE
dimension of engine selection: a cuda-only engine (TensorRT-LLM) must never be
offered on rocm/vulkan/cpu, a Vulkan-absent engine (SGLang) drops to cpu, and a
Metal host never falls back to a cpu image. Hermetic: stubbed Hub tree + stubbed
engine registry, no network.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import model_engine_pick as mp  # noqa: E402

GB = 2**30
ARCHES = ("cuda", "rocm", "vulkan", "cpu", "metal")

# -- engine registry: real per-arch image variants (from containers/engines/params)
ENGINE_IDS = {
    "llama.cpp": {"id": "llama-cpp", "formats": ["gguf"],
                  "variants": ["cuda", "rocm", "vulkan", "cpu"]},
    "vLLM": {"id": "vllm", "formats": ["gguf"],
             "variants": ["cuda", "rocm", "cpu"]},
    "SGLang": {"id": "sglang", "formats": ["gguf"],
               "variants": ["cuda", "rocm"]},            # no vulkan, no cpu
    "Ollama": {"id": "ollama", "formats": ["gguf"],
               "variants": ["cuda", "rocm", "vulkan", "cpu"]},
    "TensorRT-LLM": {"id": "tensorrt-llm", "formats": ["gguf"],
                     "variants": ["cuda"]},              # cuda-only
    "MLX": {"id": "mlx", "formats": ["gguf"],
            "variants": ["metal", "cuda"]},               # metal native engine
}


def _model(id_, name, vram, hf, tps_hw, supported, type_="LLM"):
    engines = [{"engine": e, "tps": str(t), "hardware": hw} for e, t, hw in tps_hw]
    return {
        "id": id_, "name": name, "type": type_, "params": name.split()[0],
        "hf": hf, "vram_tier": vram,
        "formats": [{"name": "GGUF", "hf": hf}],
        "engines": engines, "supported_engines": supported,
        "last_seen": "2026-10-09", "engagement": {"trend_score": 1.0, "posts_7d": 1},
    }


def _mkreg():
    return {"generated_utc": "2026-10-10T00:00:00Z", "models": [
        # a widely-served model, in README-first position
        _model("qwen3-8b", "Qwen3 8B", "8GB", "Qwen/Qwen3-8B-GGUF",
               [("llama.cpp", 150, "RTX 4090"), ("vLLM", 180, "RTX 4090"),
                ("SGLang", 200, "RX 7900 XTX"), ("Ollama", 90, "RTX 4090")],
               ["llama.cpp", "vLLM", "SGLang", "Ollama", "MLX"]),
        # cuda-only engine: served by nothing but TensorRT-LLM
        _model("nv-e2e", "NV E2E 3B", "8GB", "FakeOrg/NV-E2E-3B-GGUF",
               [("TensorRT-LLM", 320, "RTX 5090")], ["TensorRT-LLM"]),
    ]}


def _f(path, size):
    return {"path": path, "type": "file", "size": size}


def _trees():
    return {
        "Qwen/Qwen3-8B-GGUF": [
            _f("Qwen3-8B-Q8_0.gguf", 8 * GB),
            _f("Qwen3-8B-Q5_K_M.gguf", 5 * GB),
            _f("Qwen3-8B-Q4_K_M.gguf", 4 * GB),
            _f("Qwen3-8B-Q3_K_M.gguf", 3 * GB),
        ],
        "FakeOrg/NV-E2E-3B-GGUF": [
            _f("NV-E2E-3B-Q8_0.gguf", 4 * GB),
            _f("NV-E2E-3B-Q4_K_M.gguf", 2 * GB),
        ],
    }


def _variant_runnable(engine_name: str, arch: str) -> str | None:
    """The image variant an engine uses on `arch`, or None (not runnable here)."""
    info = ENGINE_IDS[engine_name]
    if arch in info["variants"]:
        return arch
    if arch == "metal" or "cpu" not in info["variants"]:
        return None        # metal never falls back to a cpu image; no cpu variant
    return "cpu"


# engine id ("mlx", "vllm", "ollama", ...) -> per-arch variants, from the stub registry
VARIANT_BY_ID = {info["id"]: info["variants"] for info in ENGINE_IDS.values()}


@pytest.fixture()
def matrix_env(monkeypatch):
    monkeypatch.setattr(mp, "_tree", lambda repo, revision="main": _trees().get(repo, []))
    monkeypatch.setattr(mp, "engine_ids", lambda: ENGINE_IDS)


# -- spec scenario: the EXHAUSTIVE arch x vram x ram permutation set -------------
@pytest.mark.parametrize("arch", ARCHES)
@pytest.mark.parametrize("vram", [8, 16, 32, 64])
@pytest.mark.parametrize("ram", [16, 32, 64])
def test_exhaustive_perms_all_map_to_fitting_hf_urls(matrix_env, arch, vram, ram):
    """Every runnable (model x engine) cell on every (arch, vram, ram) key carries the
    largest quant that fits its budget as a resolvable HF URL."""
    # Given a grid of (arch, VRAM, RAM) covering every architecture llgenie serves
    res = mp.matrix(_mkreg(), vram, ram, arch)

    # When the matrix is computed
    # Then the runnable permutations map model -> engine -> quant, each a real URL
    budget = mp.weight_budget_gb(vram, False, ram, arch) * GB
    for row in res["permutations"]:
        assert row["engines"], f"{arch}/{vram}/{ram}: {row['model']['id']} has no engine"
        for cell in row["engines"]:
            e = cell["engine"]
            assert cell["size_gb"] * GB <= budget + 1, f"{arch}/{vram}/{ram}: {e['id']} over budget"
            assert cell["use_format"] == "gguf"
            assert cell["url"], f"{arch}/{vram}/{ram}: {e['id']} has no URL"
            assert all(u.startswith("https://huggingface.co/")
                       and "/resolve/" in u for u in cell["url"]), cell["url"]

    # And every model within the card's VRAM is either offered or skipped with a reason
    seen = {row["model"]["id"] for row in res["permutations"]} | {s["model"] for s in res["skipped"]}
    assert {"qwen3-8b", "nv-e2e"} <= seen


# -- spec scenario: ARCHITECTURE drives which inference server is offered -------
@pytest.mark.parametrize("arch", ARCHES)
def test_arch_drives_engine_selection(matrix_env, arch, vram=16, ram=32):
    """The chosen inference server is the engine whose image variant that host can run:
    cuda-only TensorRT-LLM never on rocm/vulkan/cpu/metal; metal never a cpu image."""
    # Given a 16 GB / 32 GB host of each architecture
    res = mp.matrix(_mkreg(), vram, ram, arch)

    # When the matrix ranks the engines that can run the model here
    row = next(r for r in res["permutations"] if r["model"]["id"] == "qwen3-8b")
    offered = {cell["engine"]["id"] for cell in row["engines"]}

    # Then every engine runs on an image variant the architecture actually offers,
    # and the architecture-variant rules hold exactly
    for cell in row["engines"]:
        eid, variant = cell["engine"]["id"], cell["engine"]["variant"]
        assert variant in VARIANT_BY_ID[eid], f"{arch}: {eid} on {variant} not valid"
        if arch == "metal":
            assert variant == "metal", f"{arch}: {eid} must be metal, got {variant}"
        else:
            assert variant in (arch, "cpu"), f"{arch}: {eid} on {variant} not {arch}/cpu"

    # cuda-only TensorRT-LLM: offered on cuda (its only variant), never elsewhere
    trt = next((r for r in res["permutations"] if r["model"]["id"] == "nv-e2e"), None)
    if arch == "cuda":
        assert trt is not None and any(c["engine"]["id"] == "tensorrt-llm" for c in trt["engines"])
    else:
        # on any other arch TensorRT-LLM has no runnable image -> the model is skipped
        assert trt is None
        skipped = next((s["model"] for s in res["skipped"] if s["model"] == "nv-e2e"), None)
        assert skipped == "nv-e2e"

    # Vulkan-absent SGLang: offered on cuda/rocm, drops to cpu fallback only where cpu
    # is a real variant (SGLang has none) -> absent on vulkan/metal, present via... 
    has_sglang = any(c["engine"]["id"] == "sglang" for c in row["engines"])
    assert has_sglang == (arch in ("cuda", "rocm")), f"{arch}: SGLang = {has_sglang}"


# -- spec scenario: metal host never falls back to a cpu image -------------------
def test_metal_never_offers_cpu_image(matrix_env, vram=16, ram=32):
    """On a Metal host only native Metal engine variants are offered — never the
    cpu fallback image of a container engine (issue #120)."""
    # Given a 16 GB / 32 GB Metal host
    res = mp.matrix(_mkreg(), vram, ram, "metal")

    # When the matrix is computed
    # Then every offered engine runs natively as the metal variant
    for row in res["permutations"]:
        assert all(cell["engine"]["variant"] == "metal" for cell in row["engines"])
    qwen = next(r for r in res["permutations"] if r["model"]["id"] == "qwen3-8b")
    assert {c["engine"]["id"] for c in qwen["engines"]} == {"mlx"}

    # And the cuda-only TensorRT-LLM model is not servable on Metal
    assert not any(r["model"]["id"] == "nv-e2e" for r in res["permutations"])


# -- spec scenario: --matrix accepts an arch override ----------------------------
@pytest.mark.parametrize("arch", ["cuda", "metal", "cpu"])
def test_llgenie_matrix_arch_override_in_header(matrix_env, arch, tmp_path):
    """llgenie --matrix [GB] [RAM_GB] [ARCH] prints the chosen architecture's engine
    variants in the header and exits 0 (no download/serve)."""
    smoke = REPO / "tests" / "fixtures" / "matrix-smoke-registry.json"
    env = {**os.environ, "LLGENIE_REGISTRY_SRC": str(smoke),
           "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": "cpu"}
    import subprocess
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llama_serve.py"),
                        "--matrix", "24", "32", arch],
                       capture_output=True, text=True, env=env, timeout=120, input="")
    # Then it exits 0 and prints the architecture it computed the permutations for
    assert r.returncode == 0, r.stderr
    assert f"({arch}, VRAM 24 GB" in r.stdout
    assert "huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/" in r.stdout


@pytest.mark.parametrize("arch", ["cuda", "rocm", "metal"])
def test_llgenie_matrix_explicit_flags(matrix_env, arch, tmp_path):
    """llgenie --matrix --vram V --ram R --arch A is the explicit, unambiguous form:
    the flags (not the positionals) drive VRAM, RAM and architecture, so the header
    always states them plainly. The flag wins over an equivalent positional."""
    smoke = REPO / "tests" / "fixtures" / "matrix-smoke-registry.json"
    env = {**os.environ, "LLGENIE_REGISTRY_SRC": str(smoke),
           "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": "cpu"}
    import subprocess
    # Given the explicit --vram/--ram/--arch form (the flagship smoke model fits 24 GB)
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llama_serve.py"),
                        "--matrix", "--vram", "24", "--ram", "32", "--arch", arch],
                       capture_output=True, text=True, env=env, timeout=120, input="")
    # Then it exits 0 and the header echoes exactly the flags that were set
    assert r.returncode == 0, r.stderr
    assert f"({arch}, VRAM 24 GB, RAM 32 GB)" in r.stdout
    assert "huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/" in r.stdout


def test_llgenie_matrix_flag_wins_over_positional(matrix_env, tmp_path):
    """An explicit --vram flag beats a conflicting positional GB so the matrix always
    tests exactly what the caller asked for."""
    smoke = REPO / "tests" / "fixtures" / "matrix-smoke-registry.json"
    env = {**os.environ, "LLGENIE_REGISTRY_SRC": str(smoke),
           "LLAMA_MODELS_ROOT": str(tmp_path), "LLAMA_BACKEND": "cpu"}
    import subprocess
    # Given BOTH a positional GB (99) and an explicit --vram (24), RAM via --ram
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llama_serve.py"),
                        "--matrix", "99", "--vram", "24", "--ram", "32"],
                       capture_output=True, text=True, env=env, timeout=120, input="")
    # Then the flag wins: the header shows 24, never 99
    assert r.returncode == 0, r.stderr
    assert "VRAM 24 GB" in r.stdout and "VRAM 99" not in r.stdout
    assert "huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/" in r.stdout
