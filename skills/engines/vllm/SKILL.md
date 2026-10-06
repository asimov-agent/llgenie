---
name: engine-vllm
description: "Use when building the vLLM engine image (CUDA wheel matching the image toolkit, ROCm py3.12 wheel index, or CPU wheel) and serving as llm-local."
engine: "vLLM"
id: vllm
repo: https://github.com/vllm-project/vllm
ref: v0.31.0
ref_kind: tag
version: v0.31.0
pinned: db9527a46873454610df6dbedf79a36d6bf1a7f6
verified: "2026-10-05"
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
install:
  cuda:
    - "uv pip install --system --break-system-packages vllm=={version} --torch-backend={torch_backend}"
  rocm:
    - "uv pip install --system --break-system-packages vllm=={version} --extra-index-url https://wheels.vllm.ai/rocm/ --upgrade"
  cpu:
    - "uv pip install --system --break-system-packages https://github.com/vllm-project/vllm/releases/download/v{version}/vllm-{version}+cpu-cp38-abi3-manylinux_2_39_{machine}.whl --torch-backend cpu"
binary: "vllm"
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
container:                       # official upstream images already contain vLLM
  cuda:
    base: "vllm/vllm-openai:v{version}"
    prebuilt: true
  rocm:
    base: "vllm/vllm-openai-rocm:v{version}"
    prebuilt: true
  cpu:
    base: "vllm/vllm-openai-cpu:v{version}"
    prebuilt: true
upstream_watch: [pyproject.toml, requirements/cuda.txt, requirements/rocm.txt, requirements/cpu.txt, docs/getting_started/installation/gpu.md, docs/getting_started/installation/cpu.md, docker/Dockerfile.rocm_base]
---

# vLLM

Installed with `uv pip install --system` into the engine image's own Python (the container is the isolation; nothing is installed on the host).

## Hardware parameters

| Backend | Selection | Notes |
|---|---|---|
| cuda | `--torch-backend=auto` picks the PyTorch wheel index from the installed **driver** | compute capability >= 7.5. Blackwell needs CUDA >= 12.8 |
| rocm | `https://wheels.vllm.ai/rocm/` index, **Python 3.12 only** (other versions silently fall back to the CUDA wheel) | gfx90a/942/950, RDNA3 gfx1100/1101, RDNA4 gfx1200/1201, Ryzen AI gfx1150/1151 (ROCm >= 7.0.2). Source builds: `PYTORCH_ROCM_ARCH={gpu_targets}` |
| cpu | release wheel `+cpu` for the machine arch (`x86_64`/`aarch64`) | AVX2/AVX512 or NEON |

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
