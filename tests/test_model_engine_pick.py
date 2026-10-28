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
import hf_auth  # noqa: E402
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
    assert lz["measured_on"] == "ROCm" and lz["rank"] == 3
    ranks = [r["rank"] for r in rows]
    assert ranks == sorted(ranks) and ranks[0] == 0  # every CUDA-measured engine before any other


def test_models_fit_the_card_and_need_a_runnable_engine(reg):
    # Given an 8 GB CPU host
    rows = mp.rank_models(reg, "cpu", 8)
    # When the registry is ranked
    ids = [r["model"]["id"] for r in rows]
    # Then nothing outside the card's fit is offered, each row has an engine, and the
    # registry's (= the README's trend) order is kept. The fit is the product's own
    # decision (`mp.fits`: the store's measured `vram_min`, else the display `vram_tier`),
    # never a re-derivation from one field — issue #669.
    assert ids and "qwen3.8-27b" not in ids
    assert all(mp.fits(r["model"], 8) and r["engines"] for r in rows)
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
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llgenie_serve.py"),
                        "--pick", "--auto", "--dry", "--engine", "vllm"],
                       capture_output=True, text=True, env=env,
                       timeout=hf_auth.TOP_TIER_DRY_RUN_TIMEOUT)
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
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llgenie_serve.py"), "--pick", "bonsai",
                        "--engine", "prism", "--model-file", str(f), "--auto", "--dry"],
                       capture_output=True, text=True, env=env,
                       timeout=hf_auth.TOP_TIER_DRY_RUN_TIMEOUT)
    # Then it serves exactly that file with the Prism start script, no download
    assert r.returncode == 0, r.stderr
    assert "llama.cpp (PrismML fork)" in r.stdout and str(f) in r.stdout
    assert "llgenie-engine-llama-cpp-prism" in r.stdout and "download" not in r.stdout


def test_model_file_labels_the_file_not_a_registry_model(tmp_path):
    """`--model-file` serves a file the user named: print ITS name, not a trend row's.

    It used to print the registry row that ranked the engines — `--model-file
    qwen2.5-0.5b-instruct-q4_0.gguf` announced "Model : Qwen3.8-27B", which reads
    as if a 27B model were about to be served.
    """
    # Given a GGUF whose name matches no trend row
    f = tmp_path / "my-own-model-Q4_K_M.gguf"
    f.write_bytes(b"GGUF")
    env = {**os.environ, "LLGENIE_REGISTRY_SRC": str(FIXTURE), "LLAMA_MODELS_ROOT": str(tmp_path),
           "LLAMA_BACKEND": "cuda", "LLAMA_RAM_BYTES": str(16 * 2**30)}
    # When llgenie serves exactly that file
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "llgenie_serve.py"), "--pick", "bonsai",
                        "--engine", "prism", "--model-file", str(f), "--auto", "--dry"],
                       capture_output=True, text=True, env=env,
                       timeout=hf_auth.TOP_TIER_DRY_RUN_TIMEOUT)
    # Then the Model line names the FILE, and the trend row is credited only for the ranking
    assert r.returncode == 0, r.stderr
    model_line = next(ln for ln in r.stdout.splitlines() if ln.startswith("Model  :"))
    assert f.name in model_line, model_line
    assert "only ranked the inference servers" in r.stdout


def test_disabled_images_are_never_offered(reg):
    """Issue #103: a disabled engine x arch image is not offered by the picker."""
    import scripts.engine_image as ei
    for m in reg["models"]:
        for arch in ("cpu", "cuda", "rocm", "vulkan"):
            for r in mp.rank_engines(m, arch):
                assert not ei.disabled(r["id"], r["variant"]), (m["id"], arch, r)

# ------------------------------------- an engine with no downloadable plan is not offered (#750)
# `rank_engines` used to offer an engine on the strength of a t/s measurement alone, so the pick
# could hand a user a model it cannot fetch (`MLX` on the ternary Bonsai rows, `vLLM` on an
# MLX-only repo — 12 cells on the 2026-10-27 store). The committed table says what can actually
# be downloaded; for a model it covers, an engine with no cell has no plan.
def _catalog_file(tmp_path, cells):
    import json
    f = tmp_path / "catalog.json"
    f.write_text(json.dumps({"meta": {"generated_utc": "2026-01-01T00:00:00Z"}, "files": cells}))
    return f


def _measured_model(mid="m-no-plan"):
    return {"id": mid, "name": "M", "hf": "org/m", "vram_min": "4GB",
            "formats": [{"name": "GGUF", "hf": "org/m-GGUF"}],
            "engines": [{"engine": "llama.cpp", "tps": "40", "hardware": "RTX 4090"},
                        {"engine": "MLX", "tps": "90", "hardware": "M5 Max"}],
            "supported_engines": []}


def test_an_engine_with_no_catalog_cell_is_not_offered_for_a_covered_model(tmp_path, monkeypatch):
    """A measurement says somebody ran it; the table says whether this host can download it."""

    # Given a model the committed table covers with llama.cpp only, and a measurement on MLX too
    cat = _catalog_file(tmp_path, {"m-no-plan": {"llama.cpp": {"arch": ["cuda"], "quants": [
        {"repo": "org/m-GGUF", "revision": "main", "path": "m-Q4.gguf", "files": ["m-Q4.gguf"],
         "size_gb": 4.0, "url": "https://huggingface.co/org/m-GGUF/resolve/main/m-Q4.gguf"}]}}})
    monkeypatch.setenv("LLGENIE_QUANT_CATALOG", str(cat))
    monkeypatch.setattr(mp, "_QUANT_CATALOG_CACHE", None, raising=False)

    # When  the engines are ranked for a CUDA host
    rows = mp.rank_engines(_measured_model(), "cuda")

    # Then  only the engine the table can plan is offered
    assert [r["engine"] for r in rows] == ["llama.cpp"]


def test_a_model_the_catalog_does_not_cover_keeps_its_engines(tmp_path, monkeypatch):
    """A store synced a step before its catalog must still be served (live resolution)."""

    # Given a table rendered for OTHER models, and the same measured model
    cat = _catalog_file(tmp_path, {"some-other-model": {"llama.cpp": {"arch": ["cuda"], "quants": []}}})
    monkeypatch.setenv("LLGENIE_QUANT_CATALOG", str(cat))
    monkeypatch.setattr(mp, "_QUANT_CATALOG_CACHE", None, raising=False)

    # When  the engines are ranked
    rows = mp.rank_engines(_measured_model("m-uncatalogued"), "cuda")

    # Then  nothing is refused for a model the table has not been rendered for
    assert {r["engine"] for r in rows} == {"llama.cpp", "MLX"}


# ------------------------------- a fork-only quantisation picks the fork's engine
# Ternary Bonsai 2's PQ2_0 file stores ggml type 142, which exists only in the Prism fork.
# The picker used to go by the .gguf extension alone and offered stock llama.cpp, whose
# server dies on load ("tensor 'output.weight' has invalid ggml type 142") — a guaranteed
# failed start that only showed up after the container was gone.
def _write_gguf(path, tensor_type: int) -> None:
    """A minimal GGUF header: magic, version 3, one tensor of `tensor_type`, no metadata."""
    import struct
    name = b"output.weight"
    path.write_bytes(
        b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 1) + struct.pack("<Q", 0)
        + struct.pack("<Q", len(name)) + name + struct.pack("<I", 1) + struct.pack("<Q", 1)
        + struct.pack("<I", tensor_type) + struct.pack("<Q", 0))


def test_a_prism_only_tensor_type_narrows_the_engines_to_prism(tmp_path):
    """The file's own tensor types decide the engine, not the extension."""

    # Given a GGUF that stores the Prism-only PQ2_0 type and one that stores a stock type
    prism = tmp_path / "ternary-PQ2_0.gguf"
    plain = tmp_path / "plain-Q4_0.gguf"
    _write_gguf(prism, 142)
    _write_gguf(plain, 2)

    # When  the header is read
    assert mp.gguf_tensor_types(prism) == {142}
    assert mp.gguf_needs_prism(prism) is True
    assert mp.gguf_needs_prism(plain) is False

    # Then  only the Prism engine is offered for the ternary file, and every engine stays
    #       offered for the stock one
    prism_ids = {e["id"] for e in mp.engines_for_file(prism, arch="cpu")}
    plain_ids = {e["id"] for e in mp.engines_for_file(plain, arch="cpu")}
    assert prism_ids == {"llama.cpp-prism"}, prism_ids
    assert "llama.cpp" in plain_ids and len(plain_ids) > 1, plain_ids


def test_an_unreadable_gguf_header_does_not_narrow_anything(tmp_path):
    """A truncated file must not silently become 'needs prism'."""

    # Given a file with the magic but nothing else
    bad = tmp_path / "broken.gguf"
    bad.write_bytes(b"GGUF")

    # When  it is read
    # Then  the types are unknown and no engine is excluded on that basis
    assert mp.gguf_tensor_types(bad) == set()
    assert mp.gguf_needs_prism(bad) is False
