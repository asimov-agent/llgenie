---
name: engine-vllm
description: "Use when building the vLLM engine image from source (clone at the pin, compile CUDA/ROCm/CPU kernels) and serving as llm-local."
engine: "vLLM"
id: vllm
repo: https://github.com/vllm-project/vllm
ref: v0.32.0
ref_kind: tag
version: v0.32.0
pinned: 5df63a7203cdb9328d824a27b682e77c7b9928be
verified: "2026-10-19"
license: Apache-2.0
servable: true
backends: [cuda, rocm, cpu]
os: [linux]
formats: [safetensors, awq, gptq, fp8, gguf]
requires:
  min_compute_cap:
    cuda: "7.5"
  gpu_targets:
    rocm: [gfx90a, gfx942, gfx950, gfx1100, gfx1101, gfx1150, gfx1151, gfx1200, gfx1201]
prereqs:
  common: [uv]
  cuda: [nvidia-smi]
  rocm: [rocminfo]
hw_flags:
  cuda:
    cuda_arch: "'-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}'"
  rocm:
    gpu_targets: "'{gpu_targets}'"
install:
  cuda:
    - "test -d {src}/.git || git clone -b {ref} --depth 1 {repo}.git {src}"
    # --no-build-isolation builds against a preinstalled torch: bump >= the sha's own
    # torch pin from the matching PyTorch repack index, then the rest of vLLM's build deps.
    - "uv pip install --system --break-system-packages torch==2.13.0 --index-url https://download.pytorch.org/whl/{torch_backend}"
    - "uv pip install --system --break-system-packages -r {src}/requirements/build/cuda.txt --index-strategy unsafe-best-match"
    - "cd {src} && CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}' VLLM_TARGET_DEVICE=cuda uv pip install --system --break-system-packages --no-build-isolation -e ."
  rocm:
    - "test -d {src}/.git || git clone -b {ref} --depth 1 {repo}.git {src}"
    # the rocm build file itself names the amd index and the torch it needs
    - "uv pip install --system --break-system-packages -r {src}/requirements/build/rocm.txt --index-strategy unsafe-best-match"
    - "cd {src} && PYTORCH_ROCM_ARCH='{gpu_targets}' VLLM_TARGET_DEVICE=rocm uv pip install --system --break-system-packages --no-build-isolation -e ."
  cpu:
    - "test -d {src}/.git || git clone -b {ref} --depth 1 {repo}.git {src}"
    - "uv pip install --system --break-system-packages -r {src}/requirements/build/cpu.txt --index-strategy unsafe-best-match"
    - "cd {src} && VLLM_TARGET_DEVICE=cpu uv pip install --system --break-system-packages --no-build-isolation -e ."
binary: "vllm"
binary_flags: ["--version", "--help"]   # the vllm CLI answers --version (cpu detect) and --help
binary_probe:
  cuda: device   # the cuda/rocm CLI probes the device at startup and fails on a GPU-less runner (CI #106)
  rocm: device
detect:
  # the cuda/rocm builds probe the device on startup and fail on a GPU-less
  # runner (CI #106); the version comes from the package instead
  cuda: "python3 -c 'from vllm import __version__ as v; print(v)'"
  rocm: "python3 -c 'from vllm import __version__ as v; print(v)'"
  cpu: "{binary} --version"
launch:
  cuda: "{binary} serve {model} --host {host} --port {port} --served-model-name {alias} --gpu-memory-utilization 0.90"
  rocm: "{binary} serve {model} --host {host} --port {port} --served-model-name {alias} --gpu-memory-utilization 0.90"
  # on CPU --gpu-memory-utilization is a share of system RAM (0.90 refused to start
  # on a 62 GiB host, CI #98); VLLM_CPU_KVCACHE_SPACE (GiB) sizes the KV cache instead
  cpu: "{binary} serve {model} --host {host} --port {port} --served-model-name {alias}"
env:
  cpu:
    VLLM_CPU_KVCACHE_SPACE: "4"
health: "GET /health"
alias_mode: flag
container:
  # every cell compiles the pinned sha on the shared devel base for that backend
  # (cuda: nvidia/cuda:13.0.2-devel, rocm: rocm/dev-ubuntu-24.04:7.0-complete,
  #  cpu: ubuntu:24.04) — no upstream vLLM wheel is installed (issue #937)
  cuda:
    apt: [python3-dev]
  rocm:
    apt: [python3-dev]
  cpu:
    apt: [python3-dev]
upstream_watch: [pyproject.toml, requirements/cuda.txt, requirements/rocm.txt, requirements/cpu.txt, docs/getting_started/installation/gpu.md, docs/getting_started/installation/cpu.md, docker/Dockerfile.rocm_base]
---

# vLLM

Built from the pinned sha on the shared devel base for the backend, installed into the engine
image's own Python with `uv pip install --no-build-isolation -e .` (the container is the
isolation; nothing is installed on the host).

## Hardware parameters

| Backend | Selection | Notes |
|---|---|---|
| cuda | compile at the pin: `uv pip install --no-build-isolation -e .` with `CMAKE_ARGS=-DCMAKE_CUDA_ARCHITECTURES` | compute capability >= 7.5, fat arch list `75;80;86;89;90;120` |
| rocm | compile at the pin: same editable install with `VLLM_TARGET_DEVICE=rocm` + `PYTORCH_ROCM_ARCH` | gfx90a/942/950, RDNA3 gfx1100/1101, RDNA4 gfx1200/1201, Ryzen AI gfx1150/1151 (ROCm >= 7.0.2) |
| cpu | compile at the pin: `VLLM_TARGET_DEVICE=cpu uv pip install --no-build-isolation -e .` | pure Python/C++ CPU build, AVX2/AVX512 or NEON |

There is no macOS GPU backend. `vllm-metal` is a separate project.

## Launch

`vllm serve <hf-id|dir> --host 127.0.0.1 --port 11434 --served-model-name llm-local`.
The default host is `0.0.0.0`, so always pass `--host`. Tune with `--max-model-len`,
`--gpu-memory-utilization`, `--kv-cache-dtype fp8` and `--quantization`. GGUF loading is limited.
Prefer safetensors/AWQ/GPTQ. Routes: `/v1/chat/completions`, `/v1/completions`,
`/v1/models`, `/health`.

## Pitfall: VRAM held by another server

`--gpu-memory-utilization` is a share of **total** VRAM, and vLLM refuses to start
when that much is not free (`Free memory on device cuda:0 (1.31/15.6 GiB) on startup
is less than desired GPU memory utilization`). Even a small value can hit
`torch.OutOfMemoryError` while the CUDA context loads. This was seen on an RTX 4090
Laptop while a llama-server held 14 GB. Stop the other server on the GPU first: llgenie
serves one model at a time on the port. Do not lower the utilization until it fits.
