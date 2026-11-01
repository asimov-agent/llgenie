"""Unit tests for the host engine serve command (scripts/engine_host_test.py, `make test-engine-host`).

These are hermetic: the host-arch grid and the t/s measurement are exercised through the script's
own seams (env-driven hardware detection and crafted /v1/chat/completions bodies), never by really
serving a GPU image or building one. Issue #1322.
"""
from __future__ import annotations

import json
import os
import types
import urllib.error
from pathlib import Path

import pytest

from scripts import engine_host_test as eht


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


def test_model_parameter_selects_what_is_served(monkeypatch):
    """The owner-refined ENGINE/ARCH/MODEL parameterization: a supplied MODEL is served exactly,
    and is threaded through serve_published (never silently replaced by the smallest default)."""
    calls = {}
    def _run(spec, model, port, name, models_dir, wait):
        calls["model"] = model
        return 0
    def _pull(spec):
        return "tag"
    monkeypatch.setattr(eht.ei, "pull_published", _pull)
    monkeypatch.setattr(eht.ei, "run", _run)
    monkeypatch.setattr(eht.ei, "container_name", lambda spec: "c")
    monkeypatch.setattr(eht.smoke, "free_port", lambda: 18000)
    monkeypatch.setattr(eht, "_chat", lambda payload, port, timeout, retries=2: {
        "choices": [{"message": {"content": "hi"}}],
        "timings": {"prompt_per_second": 1.0, "predicted_per_second": 2.0}})
    # The `finally` cleanup calls the container runtime; make it hermetic (no real docker):
    monkeypatch.setattr(eht.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0))
    spec = {"id": "x", "variant": "cpu", "backend": "cpu"}
    rc = eht.serve_published(spec, "Qwen/Qwen0.5B", 18000, 30)
    assert rc == 0
    assert calls["model"] == "Qwen/Qwen0.5B", calls


def test_smallest_model_retries_transient_503(monkeypatch):
    """A transient Hub 503/5xx during the model fetch is retried, not fatal (measured in the sweep)."""
    calls = {"n": 0}
    monkeypatch.setattr(eht.time, "sleep", lambda s: None)  # no real backoff wait in test
    def _flakey(fmt):
        calls["n"] += 1
        if calls["n"] < 3:
            from http.client import HTTPMessage
            raise urllib.error.HTTPError("url", 503, "Service Unavailable", HTTPMessage(), None)
        return "/ok/model"
    monkeypatch.setattr(eht.smoke, "fetch_model", _flakey)
    skill = {"id": "x", "formats": ["gguf"]}
    monkeypatch.setattr(eht.smoke, "pick_format", lambda s: "gguf")
    assert eht.smallest_model(skill) == "/ok/model"
    assert calls["n"] == 3, calls


def test_smallest_model_exits_after_permanent_failure(monkeypatch):
    """A permanently failing model fetch exits after 3 attempts (never an infinite retry)."""
    calls = {"n": 0}
    monkeypatch.setattr(eht.time, "sleep", lambda s: None)
    def _always_fail(fmt):
        calls["n"] += 1
        raise SystemExit("[smoke] FAIL gguf: the model download exited 1")
    monkeypatch.setattr(eht.smoke, "fetch_model", _always_fail)
    monkeypatch.setattr(eht.smoke, "pick_format", lambda s: "gguf")
    with pytest.raises(SystemExit):
        eht.smallest_model({"id": "x", "formats": ["gguf"]})
    assert calls["n"] == 3, calls
