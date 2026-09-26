"""Unit tests for scripts/detect_server.py.

These are hermetic: they monkeypatch the real hardware probes
(`nvidia-smi` / `sysctl` / `uname` / `shutil.which` / file reads) so the
logic runs identically on any host, and they use the env-var seams
(LLAMA_BACKEND, LLAMA_RAM_BYTES, LLAMA_SERVER_TREE) exactly as the CI variant
jobs and `make install` do.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
Every requirement in openspec/changes/feat-server-clone-build/specs/llama-serving/
spec.md is exercised here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import scripts.detect_server as ds


GB = 1024 ** 3


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Start each test with no detection seams set, so overrides don't leak."""
    monkeypatch.setenv("LLAMA_BACKEND", "")
    monkeypatch.setenv("LLAMA_RAM_BYTES", "")
    monkeypatch.setenv("LLAMA_SERVER_TREE", "")
    yield


def _patch_env(monkeypatch, backend: str, ram_gb: float, tree: str):
    """Set the three detection seams (backend, RAM in bytes, tree)."""
    monkeypatch.setenv("LLAMA_BACKEND", backend)
    monkeypatch.setenv("LLAMA_RAM_BYTES", str(int(ram_gb * GB)))
    monkeypatch.setenv("LLAMA_SERVER_TREE", tree)


class _Fakes:
    """Shared fake-tool helpers for backend tests."""

    @staticmethod
    def patch(monkeypatch, nvidia: bool, nvcc: bool,
              machinetype: str = "", sys_platform: str = "linux"):
        gpu_list = "GPU 0: NVIDIA GeForce RTX 4090 Laptop GPU (16 GB)" if nvidia else ""
        has_nvcc = nvcc
        sys_p = sys_platform

        def _nvidia_gpu_list():
            return gpu_list

        def _macos_silicon():
            return machinetype == "arm64"

        monkeypatch.setattr(ds, "_nvidia_gpu_list", _nvidia_gpu_list)
        monkeypatch.setattr(ds, "_macos_silicon", _macos_silicon)
        monkeypatch.setattr(ds, "_has_nvidia_gpu",
                            lambda: len(gpu_list.splitlines()) >= 1 and has_nvcc)

        def which(name):
            if name == "nvidia-smi" and not nvidia:
                return None
            if name == "nvcc" and not has_nvcc:
                return None
            return f"/bin/{name}" if name != "nvcc" else "/opt/cuda/bin/nvcc"

        monkeypatch.setattr(ds, "_which", which)
        monkeypatch.setenv("LLAMA_BACKEND", "")
        monkeypatch.setattr(sys, "platform", sys_p)
        return gpu_list


# ---------------------------------------------------------------------------
# choose_tree: card-size decision (the #84 rule, 24 GB inclusive)
# ---------------------------------------------------------------------------
def test_choose_tree_24gb_inclusive_is_prism():
    """The boundary is inclusive: 24 GB -> Prism (the <= 24 GB rule)."""
    # Given exactly 24 GB of card RAM
    ram = 24 * GB
    # When choose_tree(24 GB) is called
    tree = ds.choose_tree(ram)
    # Then the prism tree (<= 24 GB) is selected
    assert tree == "prism"


def test_choose_tree_25gb_is_upstream():
    """Just past the boundary: 25 GB -> upstream (the > 24 GB rule)."""
    # Given exactly 25 GB of card RAM
    ram = 25 * GB
    # When choose_tree(25 GB) is called
    tree = ds.choose_tree(ram)
    # Then the upstream tree (> 24 GB) is selected
    assert tree == "upstream"


def test_choose_tree_16gb_is_prism():
    """A low-end 16 GB card -> prism (within the <= 24 GB Prism range)."""
    # Given a 16 GB card
    ram = 16 * GB
    # When choose_tree(16 GB) is called
    tree = ds.choose_tree(ram)
    # Then prism is selected
    assert tree == "prism"


def test_choose_tree_8gb_is_prism():
    """An 8 GB card -> prism (the lowest documented tier)."""
    # Given an 8 GB card
    ram = 8 * GB
    # When choose_tree(8 GB) is called
    tree = ds.choose_tree(ram)
    # Then prism is selected
    assert tree == "prism"


def test_choose_tree_64gb_is_upstream():
    """A 64 GB card (> 24 GB) -> upstream."""
    # Given a 64 GB card
    ram = 64 * GB
    # When choose_tree(64 GB) is called
    tree = ds.choose_tree(ram)
    # Then upstream is selected
    assert tree == "upstream"


def test_choose_tree_override_forces_tree_independently_of_ram():
    """The LLAMA_SERVER_TREE override forces a specific tree for CI explicit-variant
    builds, regardless of the card size."""
    # Given an 8 GB card (which would normally pick prism) forced to upstream
    ram_small = 8 * GB
    tree_up = ds.choose_tree(ram_small, override="upstream")
    # Given a 64 GB card (which would normally pick upstream) forced to prism
    ram_large = 64 * GB
    tree_pr = ds.choose_tree(ram_large, override="prism")
    # Then the override wins in both cases
    assert tree_up == "upstream"
    assert tree_pr == "prism"


def test_choose_tree_unknown_override_falls_back_to_ram():
    """An unrecognized override is ignored, so we never pick a bad tree."""
    # Given an 8 GB card and a bogus override value
    ram = 8 * GB
    tree = ds.choose_tree(ram, override="not-a-tree")
    # Then the RAM-based decision stands (prism for 8 GB)
    assert tree == "prism"


# ---------------------------------------------------------------------------
# tree_path / tree_branch / tree_url: the clone target
# ---------------------------------------------------------------------------
def test_tree_paths_are_correct():
    """Both trees resolve to the correct ~/repository/git/... clone dir."""
    # Given the two trees, their clone dirs are under ~/repository/git/
    assert ds.tree_path("prism") == str(Path.home() / "repository/git/prism-llama.cpp")
    assert ds.tree_path("upstream") == str(Path.home() / "repository/git/llama.cpp")


def test_tree_branches_are_correct():
    # Given the two trees, their branch names are correct
    assert ds.tree_branch("prism") == "prism"
    assert ds.tree_branch("upstream") == "master"


def test_tree_urls_are_correct():
    # Given the two trees, their git URLs are correct
    assert ds.tree_url("prism") == "https://github.com/PrismML-Eng/llama.cpp.git"
    assert ds.tree_url("upstream") == "https://github.com/ggerganov/llama.cpp.git"


# ---------------------------------------------------------------------------
# detect_backend: hardware -> backend (mocked real tools)
# ---------------------------------------------------------------------------
def test_detect_backend_cuda_when_nvidia_and_nvcc(monkeypatch):
    # Given an NVIDIA GPU (nvidia-smi -L lists it) AND nvcc present
    _Fakes.patch(monkeypatch, nvidia=True, nvcc=True, sys_platform="linux")
    # When detect_backend() runs with no LLAMA_BACKEND override
    backend = ds.detect_backend()
    # Then cuda is selected
    assert backend == "cuda"


def test_detect_backend_cpu_when_no_nvidia(monkeypatch):
    # Given NO NVIDIA GPU (nvidia-smi empty)
    _Fakes.patch(monkeypatch, nvidia=False, nvcc=False, sys_platform="linux")
    # When detect_backend() runs with no LLAMA_BACKEND override
    backend = ds.detect_backend()
    # Then cpu (fallback) is selected
    assert backend == "cpu"


def test_detect_backend_cuda_requires_nvcc(monkeypatch):
    # Given an NVIDIA GPU is present BUT nvcc is NOT installed
    _Fakes.patch(monkeypatch, nvidia=True, nvcc=False, sys_platform="linux")
    # When detect_backend() runs with no LLAMA_BACKEND override
    backend = ds.detect_backend()
    # Then cpu (no usable CUDA compiler) is selected
    assert backend == "cpu"


def test_detect_backend_metal_on_apple_silicon(monkeypatch):
    # Given macOS + Apple Silicon (sysctl hw.machinetype == arm64)
    monkeypatch.setenv("LLAMA_BACKEND", "")
    monkeypatch.setattr(ds, "_macos_silicon", lambda: True)
    monkeypatch.setattr(ds, "_nvidia_gpu_list", lambda: "")
    monkeypatch.setattr(sys, "platform", "darwin")
    # When detect_backend() runs with no LLAMA_BACKEND override
    backend = ds.detect_backend()
    # Then metal is selected
    assert backend == "metal"


def test_detect_backend_override_wins(monkeypatch):
    # Given any hardware, an LLAMA_BACKEND override forces the backend
    _Fakes.patch(monkeypatch, nvidia=True, nvcc=True, sys_platform="linux")
    for want in ("cpu", "cuda", "metal"):
        # When LLAMA_BACKEND is set to 'want'
        monkeypatch.setenv("LLAMA_BACKEND", want)
        # detect_backend() runs with the override
        backend = ds.detect_backend()
        # Then the override wins
        assert backend == want
    monkeypatch.setenv("LLAMA_BACKEND", "")


def test_detect_backend_invalid_override_falls_back(monkeypatch):
    # Given a bogus LLAMA_BACKEND value
    monkeypatch.setenv("LLAMA_BACKEND", "nvidia")
    _Fakes.patch(monkeypatch, nvidia=False, nvcc=False, sys_platform="linux")
    # When detect_backend() runs with the invalid override
    backend = ds.detect_backend()
    # Then it falls back to the hardware decision (cpu)
    assert backend == "cpu"


# ---------------------------------------------------------------------------
# detect_card_ram_bytes: the real-tool reads (mocked) + override
# ---------------------------------------------------------------------------
def test_detect_card_ram_bytes_override_wins(monkeypatch):
    # Given a LLAMA_RAM_BYTES override (the CI/test seam)
    monkeypatch.setenv("LLAMA_RAM_BYTES", str(8 * GB))
    # When detect_card_ram_bytes() runs
    ram = ds.detect_card_ram_bytes()
    # Then the override is returned verbatim
    assert ram == 8 * GB


def test_detect_card_ram_bytes_reads_nvidia_vram(monkeypatch):
    # Given an NVIDIA GPU whose VRAM nvidia-smi reports as 16376 MiB
    monkeypatch.setenv("LLAMA_RAM_BYTES", "")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: True)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 16376 * (1024 ** 2))
    monkeypatch.setattr(sys, "platform", "linux")
    # When detect_card_ram_bytes() runs (no override)
    ram = ds.detect_card_ram_bytes()
    # Then the GPU VRAM (not system RAM) is the card RAM
    assert ram == 16376 * (1024 ** 2)
    # A ~16 GB card, within the Prism range
    assert 8 * GB <= ram < 32 * GB


def test_detect_card_ram_bytes_reads_meminfo_on_linux(monkeypatch):
    # Given a Linux /proc/meminfo with MemTotal (no GPU, no override)
    monkeypatch.setenv("LLAMA_RAM_BYTES", "")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
    monkeypatch.setattr(sys, "platform", "linux")
    # Patch the /proc/meminfo reader so it returns the MemTotal byte value.
    monkeypatch.setattr(ds, "_read_proc_meminfo", lambda: 137438948800 * 1024)
    # When detect_card_ram_bytes() reads /proc/meminfo
    ram = ds.detect_card_ram_bytes()
    # Then it equals MemTotal in bytes (137438948800 kB)
    assert ram == 137438948800 * 1024


def test_detect_card_ram_bytes_fallback_48gb(monkeypatch):
    # Given no override, no GPU, and a /proc/meminfo read that returns 0 (unreadable)
    monkeypatch.setenv("LLAMA_RAM_BYTES", "")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
    monkeypatch.setattr(sys, "platform", "linux")
    # _read_proc_meminfo returns 0 on failure (the real implementation's contract);
    # the 48 GB fallback then lives in detect_card_ram_bytes.
    monkeypatch.setattr(ds, "_read_proc_meminfo", lambda: 0)
    # When detect_card_ram_bytes() runs
    ram = ds.detect_card_ram_bytes()
    # Then the 48 GB fallback is returned
    assert ram == 48 * GB


# ---------------------------------------------------------------------------
# detect_all: full composition (tree + backend + dirs + binary path)
# ---------------------------------------------------------------------------
def test_detect_all_8gb_cpu_upstream_override_tree(monkeypatch):
    # Given an 8 GB card (-> prism by RAM) and CPU backend, tree forced upstream
    _patch_env(monkeypatch, backend="cpu", ram_gb=8, tree="upstream")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
    # When detect_all() runs
    r = ds.detect_all()
    # Then tree=upstream (override), backend=cpu, build dir=build-cpu
    assert r["tree"] == "upstream"
    assert r["backend"] == "cpu"
    assert r["build_dir"] == "build-cpu"
    assert "-DGGML_METAL=OFF" in r["cmake_flags"]
    # The binary path must be under the upstream tree dir
    assert "prism-llama.cpp" not in r["binary_path"]
    assert r["binary_path"].endswith("llama.cpp/build-cpu/bin/llama-server")


def test_detect_all_prism_cuda_build_dir_and_flags(monkeypatch):
    # Given a 16 GB card and cuda backend, explicit prism tree
    _patch_env(monkeypatch, backend="cuda", ram_gb=16, tree="prism")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: True)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 16 * GB)
    # When detect_all() runs
    r = ds.detect_all()
    # Then tree=prism, backend=cuda, build dir=build-cuda
    assert r["tree"] == "prism"
    assert r["backend"] == "cuda"
    assert r["build_dir"] == "build-cuda"
    assert "-DGGML_CUDA=ON" in r["cmake_flags"]
    assert "-DGGML_METAL=OFF" in r["cmake_flags"]
    # The binary path must be under the prism tree dir
    assert "prism-llama.cpp/build-cuda/bin/llama-server" in r["binary_path"]


def test_detect_all_metal_build_dir(monkeypatch):
    # Given an 8 GB card and metal backend
    _patch_env(monkeypatch, backend="metal", ram_gb=8, tree="prism")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
    # When detect_all() runs
    r = ds.detect_all()
    # Then tree=prism, backend=metal, build dir=build-metal
    assert r["tree"] == "prism"
    assert r["backend"] == "metal"
    assert r["build_dir"] == "build-metal"
    assert "-DGGML_METAL=ON" in r["cmake_flags"]
    assert "-DGGML_CUDA=OFF" in r["cmake_flags"]
    assert "prism-llama.cpp/build-metal/bin/llama-server" in r["binary_path"]


# ---------------------------------------------------------------------------
# detect_all: the threshold boundary through the full pipeline
# ---------------------------------------------------------------------------
def test_detect_all_threshold_24gb_inclusive_via_env(monkeypatch):
    """End-to-end: exactly 24 GB card -> prism (inclusive boundary)."""
    # Given exactly 24 GB of card RAM
    _patch_env(monkeypatch, backend="cpu", ram_gb=24, tree="")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
    # When detect_all() runs
    r = ds.detect_all()
    # Then prism is selected (24 GB is inclusive -> prism)
    assert r["tree"] == "prism"


def test_detect_all_threshold_25gb_via_env(monkeypatch):
    """End-to-end: 25 GB card -> upstream (exclusive boundary)."""
    # Given 25 GB of card RAM
    _patch_env(monkeypatch, backend="cpu", ram_gb=25, tree="")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
    # When detect_all() runs
    r = ds.detect_all()
    # Then upstream is selected (25 GB > 24 GB)
    assert r["tree"] == "upstream"


# ---------------------------------------------------------------------------
# detect_all: the backend override seam + card size independence
# ---------------------------------------------------------------------------
def test_detect_all_same_card_different_backend_different_dirs(monkeypatch):
    """The CI matrix builds the same card with multiple backends into distinct
    build dirs (build-cpu, build-cuda, build-metal) so they never collide."""
    for backend, build_dir, flag in [
        ("cpu", "build-cpu", "-DGGML_METAL=OFF"),
        ("cuda", "build-cuda", "-DGGML_CUDA=ON"),
        ("metal", "build-metal", "-DGGML_METAL=ON"),
    ]:
        # Given the same 16 GB card, forced to a different backend each time
        _patch_env(monkeypatch, backend=backend, ram_gb=16, tree="upstream")
        monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
        monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
        # When detect_all() runs for that backend
        r = ds.detect_all()
        # Then the build dir + flags match the backend
        assert r["backend"] == backend
        assert r["build_dir"] == build_dir
        assert flag in r["cmake_flags"]


def test_detect_all_tree_override_independent_of_ram(monkeypatch):
    """The CI seam: force upstream on an 8 GB card and prism on a 64 GB card."""
    # Given an 8 GB card forced to upstream
    _patch_env(monkeypatch, backend="cpu", ram_gb=8, tree="upstream")
    monkeypatch.setattr(ds, "_has_nvidia_gpu", lambda: False)
    monkeypatch.setattr(ds, "_gpu_vram_bytes", lambda: 0)
    r = ds.detect_all()
    # Then upstream is selected (override wins over the 8GB -> prism default)
    assert r["tree"] == "upstream"

    # Given a 64 GB card forced to prism
    _patch_env(monkeypatch, backend="cpu", ram_gb=64, tree="prism")
    r = ds.detect_all()
    # Then prism is selected (override wins over the 64GB -> upstream default)
    assert r["tree"] == "prism"
