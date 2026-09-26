#!/usr/bin/env python3
"""Detect which llama.cpp tree + backend to build for llgenie.

Two independent axes, each decided by calling the REAL system tools, with an
env-var override as a mock seam for CI / tests:

  Card RAM  -> tree:   card_ram <= 24 GB -> prism (superset; low-bit quants)
                      card_ram >  24 GB -> upstream (stock, standard quants)
  Hardware  -> backend:
      Metal : macOS + Apple Silicon (sysctl hw.machinetype / uname -m)
      CUDA  : nvidia-smi lists a GPU AND nvcc (the compiler) is installed
      CPU   : fallback (no usable GPU path)

"Card RAM" means the memory of the GPU card when an NVIDIA GPU is present
(`nvidia-smi --query-gpu=memory.total`), otherwise the system RAM (macOS
`hw.memsize` / Linux `/proc/meminfo MemTotal`). This matches the hardware
spec: an 8/16 GB NVIDIA card -> Prism, a >24 GB card (or a CPU box with
>24 GB RAM) -> upstream.

Env overrides (mock the hardware without touching it):
  LLAMA_BACKEND     metal | cuda | cpu
  LLAMA_RAM_BYTES   bytes
  LLAMA_SERVER_TREE prism | upstream   (forces the tree, independent of RAM;
                                          used by the parallel CI variant jobs)

Usage:
  python3 scripts/detect_server.py
  python3 scripts/detect_server.py --json
  python3 scripts/detect_server.py --backend cuda --ram-gb 16

The detection functions are plain, side-effect-free Python so they can be
imported by tests and monkeypatched.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Inclusive threshold: card_ram <= 24 GB -> Prism.
PRISM_THRESHOLD_GB = 24

PRISM_URL = "https://github.com/PrismML-Eng/llama.cpp.git"
UPSTREAM_URL = "https://github.com/ggerganov/llama.cpp.git"
PRISM_BRANCH = "prism"
UPSTREAM_BRANCH = "master"

HOME = os.path.expanduser("~")
PRISM_DIR = os.path.join(HOME, "repository/git/prism-llama.cpp")
UPSTREAM_DIR = os.path.join(HOME, "repository/git/llama.cpp")

BACKEND_CMAKE_FLAGS = {
    "metal": "-DGGML_METAL=ON -DGGML_CUDA=OFF -DGGML_SYCL=OFF -DLLAMA_CUBLAS=OFF",
    "cuda": "-DGGML_CUDA=ON -DGGML_METAL=OFF -DGGML_SYCL=OFF -DLLAMA_CUBLAS=OFF",
    "cpu": "-DGGML_METAL=OFF -DGGML_CUDA=OFF -DGGML_SYCL=OFF -DLLAMA_CUBLAS=OFF",
}
BACKEND_BUILD_DIRS = {
    "metal": "build-metal",
    "cuda": "build-cuda",
    "cpu": "build-cpu",
}

# Common CUDA-toolkit install prefixes so `nvcc` is found even when CUDA is
# not on the caller's PATH (e.g. /opt/cuda or /usr/local/cuda on Linux).
_NVCC_SEARCH = ["/opt/cuda/bin/nvcc", "/usr/local/cuda/bin/nvcc"]


# ---------------------------------------------------------------------------
# Low-level subprocess helper (single implementation, reused everywhere)
# ---------------------------------------------------------------------------
def _run(cmd, capture=True, timeout=5) -> str:
    """Run a command; return stdout (best-effort; returns '' on timeout)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def _which(name: str) -> bool:
    return shutil.which(name) is not None


# ---------------------------------------------------------------------------
# Hardware verification — calls the real tools
# ---------------------------------------------------------------------------
def _macos_silicon() -> bool:
    """True on Apple Silicon macOS. Verifies via the machine architecture
    (sysctl hw.machinetype on modern macOS) and/or uname -m."""
    if sys.platform != "darwin":
        return False
    machinetype = _run(["sysctl", "-n", "hw.machinetype"], timeout=5).strip()
    if machinetype == "arm64":
        return True
    uname = _run(["uname", "-m"]).strip()
    return uname.lower() in ("arm64", "aarch64")


def _nvidia_gpu_list() -> str:
    """Return the GPU list from nvidia-smi -L (empty string if none/no nvidia).

    nvidia-smi -L prints one line per GPU. Older versions use
    "0    RTX 4090 (16 GB)"; newer versions use
    "GPU 0: NVIDIA GeForce RTX 4090 Laptop GPU (UUID: ...)". Handle both by
    keeping any non-empty line that contains a GPU slot identifier (a leading
    digit, or a 'GPU <digit>' token).
    """
    if not _which("nvidia-smi"):
        return ""
    out = _run(["nvidia-smi", "-L"], timeout=10)
    lines = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # a real GPU line carries a slot number: "0  ..." or "GPU 0: ..."
        if re.search(r"(^GPU\s+\d+)|^\d+\s+|:.*\(UUID:", line):
            lines.append(line)
    return "\n".join(lines)


def _has_nvidia_gpu() -> bool:
    """An NVIDIA GPU is present (nvidia-smi -L lists >= 1 line)."""
    return len(_nvidia_gpu_list().splitlines()) >= 1


def _find_nvcc() -> str:
    """Return the absolute path to the nvcc compiler, or '' if none found.

    Checks PATH first, then the standard CUDA-toolkit install prefixes, so a
    CUDA build can be selected even when CUDA lives under /opt/cuda or
    /usr/local/cuda rather than being on the caller's PATH.
    """
    p = shutil.which("nvcc")
    if p:
        return p
    for d in _NVCC_SEARCH:
        if os.path.exists(d) and os.access(d, os.X_OK):
            return d
    return ""


def _has_nvcc() -> bool:
    return _find_nvcc() != ""


def _gpu_vram_bytes() -> int:
    """Return total NVIDIA GPU VRAM in bytes, or 0 if no usable query result.

    Sums `nvidia-smi --query-gpu=memory.total` across all GPUs.
    """
    if not _has_nvidia_gpu():
        return 0
    out = _run(["nvidia-smi", "--query-gpu=memory.total",
                "--format=csv,noheader"], timeout=10)
    total = 0
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r"(\d+)\s*(MiB|GiB|TiB|B)", line)
        if not m:
            continue
        val, unit = int(m.group(1)), m.group(2).lower()
        if unit == "mib":
            total += val * (1024 ** 2)
        elif unit == "gib":
            total += val * (1024 ** 3)
        elif unit == "tib":
            total += val * (1024 ** 4)
        elif unit == "b":
            total += val
    return total


def detect_backend() -> str:
    """Return 'metal' | 'cuda' | 'cpu'.

    Resolution order:
      1. $LLAMA_BACKEND override (CI / test mock)
      2. macOS + Apple Silicon  -> 'metal'
      3. nvidia-smi lists a GPU AND nvcc present -> 'cuda'
      4. otherwise -> 'cpu'
    """
    env_backend = (os.environ.get("LLAMA_BACKEND") or "").strip()
    if env_backend in ("metal", "cuda", "cpu"):
        return env_backend

    # 2. Metal: Apple Silicon on macOS
    if sys.platform == "darwin":
        if _macos_silicon():
            return "metal"
        return "cpu"  # Intel macOS: no Metal path in our scope

    # 3. CUDA: NVIDIA GPU present AND nvcc compiler available (PATH or known dirs)
    if _has_nvidia_gpu() and _has_nvcc():
        return "cuda"

    # 4. fallback
    return "cpu"


def detect_card_ram_bytes() -> int:
    """Read the 'card' RAM in bytes by calling the real tool.

    The 'card' RAM is the GPU's VRAM when an NVIDIA GPU is present
    (the hardware spec the build decision is made against), otherwise the
    system RAM. Resolution order:
      1. $LLAMA_RAM_BYTES override (CI / test mock)
      2. NVIDIA GPU present -> nvidia-smi memory.total (summed across GPUs)
      3. macOS: sysctl -n hw.memsize
      4. Linux: /proc/meminfo MemTotal
      5. fallback: 48 GB
    """
    env = (os.environ.get("LLAMA_RAM_BYTES") or "").strip()
    if env.isdigit() and int(env) > 0:
        return int(env)

    # 2. NVIDIA GPU: the card's VRAM is the relevant constraint
    vram = _gpu_vram_bytes()
    if vram > 0:
        return vram

    # 3. macOS
    if sys.platform == "darwin":
        out = _run(["sysctl", "-n", "hw.memsize"], timeout=5).strip()
        if out.isdigit():
            return int(out)
        return 48 * 1024 ** 3

    # 4. Linux
    meminfo = _read_proc_meminfo()
    if meminfo > 0:
        return meminfo

    # 5. fallback
    return 48 * 1024 ** 3  # 48 GB fallback


def _read_proc_meminfo() -> int:
    """Read total system RAM in bytes from /proc/meminfo (Linux).

    Returns 0 on failure so detect_card_ram_bytes can fall back to 48 GB.
    Extracted as a helper so tests can mock the /proc/meminfo read without
    patching the open() of a real path.
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb * 1024
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Tree + backend selection
# ---------------------------------------------------------------------------
def choose_tree(card_ram_bytes: int, override: str = "") -> str:
    """Return 'prism' or 'upstream'.

    - If ``override`` is 'prism' or 'upstream' (set via ``LLAMA_SERVER_TREE``
      env for CI explicit-variant builds), use it directly. This is the CI
      seam: it lets the pipeline verify a specific tree+backend combo
      independently of the card size.
    - Otherwise derive from card RAM: ``<= PRISM_THRESHOLD_GB (24)`` -> Prism,
      else -> upstream. The threshold is inclusive on the low side.
    """
    if override in ("prism", "upstream"):
        return override
    card_gb = card_ram_bytes / (1024 ** 3)
    return "prism" if card_gb <= PRISM_THRESHOLD_GB else "upstream"


def tree_path(tree: str) -> str:
    return PRISM_DIR if tree == "prism" else UPSTREAM_DIR


def tree_branch(tree: str) -> str:
    return PRISM_BRANCH if tree == "prism" else UPSTREAM_BRANCH


def tree_url(tree: str) -> str:
    return PRISM_URL if tree == "prism" else UPSTREAM_URL


# ---------------------------------------------------------------------------
# Aggregate detection
# ---------------------------------------------------------------------------
def detect_all() -> dict:
    """Full detection. Returns a dict usable by make / tests."""
    ram_bytes = detect_card_ram_bytes()
    card_gb = ram_bytes / (1024 ** 3)
    tree_override = (os.environ.get("LLAMA_SERVER_TREE") or "").strip()
    tree = choose_tree(ram_bytes, override=tree_override)
    backend = detect_backend()
    tree_dir = tree_path(tree)
    build_dir = BACKEND_BUILD_DIRS[backend]
    return {
        "ram_bytes": ram_bytes,
        "card_gb": round(card_gb, 2),
        "tree": tree,
        "tree_url": tree_url(tree),
        "tree_branch": tree_branch(tree),
        "tree_dir": tree_dir,
        "backend": backend,
        "backend_flags": BACKEND_CMAKE_FLAGS[backend],
        "build_dir": build_dir,
        "cmake_flags": BACKEND_CMAKE_FLAGS[backend],
        "binary_path": os.path.join(tree_dir, build_dir, "bin", "llama-server"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect llama.cpp tree + backend")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tree", choices=["prism", "upstream"], default=None,
                    help="Force tree (overrides RAM-based detection)")
    ap.add_argument("--backend", choices=["metal", "cuda", "cpu"], default=None,
                    help="Force backend (overrides hardware detection)")
    ap.add_argument("--ram-gb", type=float, default=None,
                    help="Force card RAM in GB")
    args = ap.parse_args()

    if args.backend:
        os.environ["LLAMA_BACKEND"] = args.backend
    if args.ram_gb is not None:
        os.environ["LLAMA_RAM_BYTES"] = str(int(args.ram_gb * 1024 ** 3))

    result = detect_all()
    if args.tree:
        if args.tree == "prism":
            result["tree"] = "prism"
            result["tree_url"] = PRISM_URL
            result["tree_branch"] = PRISM_BRANCH
            result["tree_dir"] = PRISM_DIR
        else:
            result["tree"] = "upstream"
            result["tree_url"] = UPSTREAM_URL
            result["tree_branch"] = UPSTREAM_BRANCH
            result["tree_dir"] = UPSTREAM_DIR
        result["binary_path"] = os.path.join(result["tree_dir"],
                                             result["build_dir"], "bin", "llama-server")

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Card RAM : {result['card_gb']} GB ({result['ram_bytes']} bytes)")
    print(f"Tree     : {result['tree']}  ({result['tree_dir']}, branch={result['tree_branch']})")
    print(f"Backend  : {result['backend']}")
    print(f"CMake    : -DCMAKE_BUILD_TYPE=Release {result['backend_flags']}")
    print(f"Build dir: {result['tree_dir']}/{result['build_dir']}")
    print(f"Binary   : {result['binary_path']}")
    print(f"\n[OK] Detected: {result['tree']} + {result['backend']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
