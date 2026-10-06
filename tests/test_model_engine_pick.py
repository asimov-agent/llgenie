"""llgenie model + inference-server pick (OpenSpec feat-model-engine-pick).

Unit tests run against the pinned registry fixture; the download test fetches a
real CHUNK of a real Hub file (HTTP Range) so CI exercises the download path
without pulling gigabytes.
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

FIXTURE = REPO / "tests" / "fixtures" / "trending-models.json"


@pytest.fixture()
def reg():
    return mp.load_registry(str(FIXTURE))


def test_engines_ranked_by_tps_then_trending_for_this_host(reg):
    # Given qwen3.8-27b, measured on several engines and kinds of hardware
    m = next(x for x in reg["models"] if x["id"] == "qwen3.8-27b")
    # When ranked for a CUDA host
    rows = mp.rank_engines(m, "cuda")
    # Then only engines with a container image run, figures measured on CUDA hardware
    # first (highest t/s first), other-hardware figures (ROCm/CPU/Metal) after, labelled
    keys = [(r["rank"], -r["tps"]) for r in rows]
    assert keys == sorted(keys)
    assert all(r["measured_on"] in ("CUDA", "ROCm", "CPU", "Metal", "") for r in rows)
    assert all(r["rank"] > 0 for r in rows if r["measured_on"] != "CUDA")
    # (an engine whose cuda image is disabled, issue #103, falls back to its cpu image)
    import scripts.engine_image as ei
    assert all(r["variant"] == ("cpu" if ei.disabled(r["id"], "cuda") else "cuda") for r in rows)
    assert all(r["measured_on"] == "Metal" for r in rows if "Apple" in r["hardware"])
    assert rows[0]["same_hw"] and rows[0]["measured_on"] == "CUDA"
    lz = next(r for r in rows if r["id"] == "llama.cpp-laurentzuijdwijk")  # Strix Halo figure only
    assert lz["measured_on"] == "ROCm" and lz["rank"] == 1
    ranks = [r["rank"] for r in rows]
    assert ranks == sorted(ranks) and ranks[0] == 0  # every CUDA-measured engine before any other


def test_models_fit_the_card_and_need_a_runnable_engine(reg):
    # Given an 8 GB CPU host
    rows = mp.rank_models(reg, "cpu", 8)
    # When the registry is ranked
    ids = [r["model"]["id"] for r in rows]
    # Then nothing above 8 GB is offered, each row has an engine, and the registry's
    # (= the README's trend) order is kept
    assert ids and "qwen3.8-27b" not in ids
    assert all(mp._num(r["model"]["vram_tier"]) <= 8 and r["engines"] for r in rows)
    order = [m["id"] for m in reg["models"]]
    assert [order.index(i) for i in ids] == sorted(order.index(i) for i in ids)


def test_auto_takes_the_top_and_engine_param_selects(reg):
    # Given the ranked engines of bonsai on a CUDA host
    rows = mp.rank_engines(next(x for x in reg["models"] if x["id"] == "qwen3.8-27b"), "cuda")
    # When --auto / an engine param is given
    # Then auto = the top one, a param selects by substring, a miss is an error
    assert mp.choose(rows, lambda r: r["id"], "engine", None, True) is rows[0]
    assert mp.choose(rows, lambda r: r["id"], "engine", "sglang", False)["id"] == "sglang"
    with pytest.raises(SystemExit):
        mp.choose(rows, lambda r: r["id"], "engine", "nope", False)


def test_local_model_is_found_under_models_dir(reg, tmp_path):
    # Given a models dir holding a Bonsai 2 27B GGUF
    (tmp_path / "x").mkdir()
    f = tmp_path / "x" / "Bonsai-2-27B-Q2.gguf"
    f.write_bytes(b"GGUF")
    m = next(x for x in reg["models"] if x["id"] == "bonsai-2-27b")
    # When resolved
    # Then that file is used (no download)
    assert mp.resolve_local(m, tmp_path) == f


def test_llgenie_dry_run_prints_model_engine_and_container_command(tmp_path):
    # Given the fixture registry and an empty models dir on a 8 GB CPU host
    env = {**os.environ, "LLGENIE_REGISTRY_SRC": str(FIXTURE), "LLAMA_MODELS_ROOT": str(tmp_path),
           "LLAMA_BACKEND": "cpu", "LLAMA_RAM_BYTES": str(8 * 2**30)}
    # When llgenie --pick --auto --dry --engine vllm runs
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llama_serve.py"),
                        "--pick", "--auto", "--dry", "--engine", "vllm"],
                       capture_output=True, text=True, env=env, timeout=120)
    # Then it picks a vllm-servable model, would download it, and serves via the engine script
    assert r.returncode == 0, r.stderr
    assert "Engine : vLLM [cpu]" in r.stdout
    assert "would download" in r.stdout
    assert "llgenie-engine-vllm" in r.stdout


def test_download_fetches_a_real_chunk_of_the_chosen_file(tmp_path, monkeypatch):
    """CI download test: the real Hub tree lookup + a ranged fetch of 1 MiB."""
    # Given a small GGUF model and a 1 MiB download cap
    monkeypatch.setenv("LLGENIE_DOWNLOAD_MAX_BYTES", str(2**20))
    model = {"id": "smoke", "name": "Qwen2.5 0.5B", "hf": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
             "formats": [{"name": "GGUF", "hf": "Qwen/Qwen2.5-0.5B-Instruct-GGUF"}]}
    # When it is downloaded for a 2 GB card
    out = mp.download(model, gb=2, root=tmp_path)
    # Then the chosen .gguf exists, holds exactly the chunk, and starts with the GGUF magic
    assert out.suffix == ".gguf" and out.parent == tmp_path / "Qwen__Qwen2.5-0.5B-Instruct-GGUF"
    assert out.stat().st_size == 2**20
    assert out.read_bytes()[:4] == b"GGUF"


def test_model_file_param_serves_that_exact_file(tmp_path):
    # Given a specific GGUF outside the auto-picked one
    f = tmp_path / "Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf"
    f.write_bytes(b"GGUF")
    env = {**os.environ, "LLGENIE_REGISTRY_SRC": str(FIXTURE), "LLAMA_MODELS_ROOT": str(tmp_path),
           "LLAMA_BACKEND": "cuda", "LLAMA_RAM_BYTES": str(16 * 2**30)}
    # When llgenie --pick bonsai --engine prism --model-file <f> --dry runs
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llama_serve.py"), "--pick", "bonsai",
                        "--engine", "prism", "--model-file", str(f), "--auto", "--dry"],
                       capture_output=True, text=True, env=env, timeout=120)
    # Then it serves exactly that file with the Prism start script, no download
    assert r.returncode == 0, r.stderr
    assert "llama.cpp (PrismML fork)" in r.stdout and str(f) in r.stdout
    assert "llgenie-engine-llama-cpp-prism" in r.stdout and "download" not in r.stdout


def test_disabled_images_are_never_offered(reg):
    """Issue #103: a disabled engine x arch image is not offered by the picker."""
    import scripts.engine_image as ei
    for m in reg["models"]:
        for arch in ("cpu", "cuda", "rocm", "vulkan"):
            for r in mp.rank_engines(m, arch):
                assert not ei.disabled(r["id"], r["variant"]), (m["id"], arch, r)
