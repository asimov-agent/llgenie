"""Unit tests for the host engine serve command (scripts/engine_host_test.py, `make test-engine-host`).

These are hermetic: the host-arch grid and the t/s measurement are exercised through the script's
own seams (env-driven hardware detection and crafted /v1/chat/completions bodies), never by really
serving a GPU image or building one. Issue #1322.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import engine_host_test as eht  # noqa: E402


@pytest.fixture(autouse=True)
def _no_caps():
    """Default: no CUDA/ROCm so the arch grid is cpu-only and fully hermetic."""
    old = {
        k: os.environ.get(k) for k in
        ("LLGENIE_CUDA_ARCH", "LLGENIE_GPU_TARGETS", "LLGENIE_RAM_BYTES", "LLAMA_BACKEND")
    }
    os.environ.pop("LLGENIE_CUDA_ARCH", None)
    os.environ.pop("LLGENIE_GPU_TARGETS", None)
    os.environ.pop("LLGENIE_RAM_BYTES", None)
    os.environ.pop("LLAMA_BACKEND", None)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_host_supported_archs_cpu_only(monkeypatch):
    """A host with no CUDA caps, no ROCm targets and no /dev/dri render node serves only cpu."""
    monkeypatch.setattr(eht.es, "nvidia_compute_caps", lambda: [])
    monkeypatch.setattr(eht.es, "rocm_gfx_targets", lambda: [])
    monkeypatch.setattr(eht, "_vulkan_render_nodes", lambda: [])
    archs = eht.host_supported_archs()
    assert archs == ["cpu"], archs


def test_host_supported_archs_cuda_when_caps(monkeypatch):
    """A host whose nvidia-smi reports compute caps adds cuda and keeps cpu."""
    monkeypatch.setattr(eht.es, "nvidia_compute_caps", lambda: ["8.9"])
    monkeypatch.setattr(eht.es, "rocm_gfx_targets", lambda: [])
    archs = eht.host_supported_archs()
    assert "cuda" in archs and "cpu" in archs, archs
    assert archs.index("cuda") < archs.index("cpu"), "cuda must serve before cpu"


def test_host_supported_archs_rocm_when_targets(monkeypatch):
    """A host with rocminfo gfx targets adds rocm and keeps cpu."""
    monkeypatch.setattr(eht.es, "nvidia_compute_caps", lambda: [])
    monkeypatch.setattr(eht.es, "rocm_gfx_targets", lambda: ["gfx1100"])
    archs = eht.host_supported_archs()
    assert "rocm" in archs and "cpu" in archs, archs


def test_measure_tps_reads_server_fields():
    """The measured t/s comes from the response's own timings / usage, never fabricated."""
    body = {
        "choices": [{"message": {"content": "hi"}}],
        "timings": {"prompt_per_second": 12.34, "predicted_per_second": 56.78},
    }
    tps = eht.measure_tps(body)
    assert tps["prompt_per_second"] == 12.34
    assert tps["predicted_per_second"] == 56.78
    # vllm-style usage field is also honoured
    body2 = {"usage": {"prompt_tokens_per_second": 9.9, "completion_tokens_per_second": 4.4}}
    tps2 = eht.measure_tps(body2)
    assert tps2["prompt_tokens_per_second"] == 9.9
    assert tps2["completion_tokens_per_second"] == 4.4


def test_measure_tps_empty_when_no_field():
    """No field in the body -> empty tps dict (the caller reports 'server reported no t/s field')."""
    assert eht.measure_tps({"choices": [{"message": {"content": "hi"}}]}) == {}


def test_engines_to_test_subset(monkeypatch):
    """The engine list comes from the committed params dir; a subset check never reddens on more."""
    fake = {
        "llama.cpp": {"id": "llama.cpp", "variants": {"cpu": {}, "cuda": {}}},
        "ollama": {"id": "ollama", "variants": {"cpu": {}}},
    }
    class _P:
        def glob(self, pat):
            assert pat == "*.json"
            for pid, data in fake.items():
                fp = types.SimpleNamespace(read_text=lambda d=data: json.dumps(d),
                                           name=f"{pid}.json")
                yield fp
    monkeypatch.setattr(eht.es, "PARAMS_DIR", _P())
    got = eht.engines_to_test(None)
    assert set(got) == {"llama.cpp", "ollama"}           # exact for the fixture
    assert {"llama.cpp", "ollama"} <= set(eht.engines_to_test(None))  # subset property
    assert set(eht.engines_to_test("llama.cpp")) == {"llama.cpp"}


def test_served_failure_returns_nonzero(monkeypatch):
    """A directly-attempted engine whose image is not published fails loudly (never a pass/skip)."""
    def _no_pull(spec):
        return ""
    monkeypatch.setattr(eht.ei, "pull_published", _no_pull)
    spec = {"id": "x", "variant": "cpu", "backend": "cpu"}
    assert eht.serve_published(spec, "model", 12345, 10) == 1
