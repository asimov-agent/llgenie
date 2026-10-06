---
name: engine-freetoken
description: "Use when installing FreeToken (big MoE on small GPUs; CUDA 13 accel wheel or experimental RDNA ROCm build) and serving `ft serve` as llm-local."
engine: "FreeToken"
id: freetoken
repo: https://github.com/FlashML-org/FreeToken
ref: v0.1.3
ref_kind: tag
version: v0.1.3
pinned: cac247a860e316e06580d05aeb05f2e647bde214
verified: "2026-10-05"
license: Apache-2.0
servable: true
backends: [cuda, rocm]
os: [linux]
formats: [safetensors, ftw, gguf]
requires:
  min_compute_cap:
    cuda: "8.0"
  min_cuda:
    cuda: "13.0"
  gpu_targets:
    rocm: [gfx1100, gfx1101, gfx1102, gfx1103, gfx1200, gfx1201]
prereqs:
  common: [uv]
  cuda: [nvidia-smi, nvcc]
  rocm: [rocminfo, git]
install:
  cuda:
    - "uv pip install --system --break-system-packages 'freetoken[accel]=={version}'"
  rocm:
    # ROCm support (hip_compat, docs/install_amd.md) is only on main after v0.1.3:
    # the v{version} tag fails with "CUDA_HOME is required" (CI #98)
    - "test -d {src}/.git || git clone {repo}.git {src}"
    - "git -C {src} fetch origin main && git -C {src} checkout -q 555efd89447232a555e05d187256b76a51c1aaa0"
    # FreeToken needs torch>=2.11,<2.12 (ROCm wheel, preinstalled for --no-build-isolation)
    - "python3 -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/rocm7.2 'torch==2.11.*'"
    - "python3 -m pip install --no-cache-dir setuptools wheel"
    - "cd {src} && ROCM_HOME=/opt/rocm CUDA_HOME=/opt/rocm PYTORCH_ROCM_ARCH='{gpu_targets}' FREETOKEN_ROCM_ARCH='{gpu_targets}' python3 -m pip install --no-cache-dir --no-build-isolation -e ."
binary: "ft"
detect: "{binary} --version"
launch: "{binary} serve --model {model} --host {host} --port {port} --served-model-name {alias} --moe-strategy auto"
health: "GET /health"
alias_mode: flag
container:
  rocm:
    base: "rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e"   # ROCm 7.2.4 (same base as sglang; the 7.14 rocm/pytorch is a 19 GB layer); torch 2.11 below
    gpu_targets: "gfx1100;gfx1101;gfx1102;gfx1103;gfx1200;gfx1201"   # RDNA3/4 only (requires.gpu_targets)
upstream_watch: [pyproject.toml, setup.py, docs/install.md, docs/install_amd.md, docs/cli.md]
---

# FreeToken

## Hardware parameters

- **cuda:** RTX 30/40/50 (sm_80/86/89/120). Driver r580+ (CUDA 13). Kernels are
  JIT-compiled on first use, so a CUDA 13 `nvcc` must be on PATH. `freetoken[accel]`
  pulls flashinfer cu13 + sglang-kernel, with torch >= 2.11,< 2.12.
- **rocm (experimental):** RDNA3/RDNA4 only (`gfx1100-1103`, `gfx1200/1201`),
  ROCm 7.14. Source build with `PYTORCH_ROCM_ARCH`/`FREETOKEN_ROCM_ARCH` = the
  detected gfx target.
- **VRAM-dependent MoE placement:** `--moe-strategy auto|fused|offload|cpu|hybrid`
  (`auto` picks offload/hybrid from a bandwidth profile), plus `--moe-cache-size`,
  `--moe-cpu-layers`, `--moe-hybrid-max-fetch`.

## Launch

`ft serve --model <dir|hf-id> --host 127.0.0.1 --port 11434 --served-model-name llm-local`
(default port 1919). Routes: `/v1/chat/completions`, `/v1/responses`,
`/v1/messages`, `/v1/models`, `/health`.
