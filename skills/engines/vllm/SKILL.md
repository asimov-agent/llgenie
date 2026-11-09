---
name: engine-vllm
description: "Use when building the vLLM engine image from source (clone at the pin, compile CUDA/ROCm/CPU kernels) and serving as llm-local."
engine: "vLLM"
id: vllm
repo: https://github.com/vllm-project/vllm
ref: v0.33.0
ref_kind: tag
version: v0.33.0
pinned: 3a4d82f569a9f57054ba81633e9b6c73b34b51fe
verified: "2026-11-02"
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
  cuda: []   # prebuilt thin image over vLLM's official CUDA serving base — zero install steps (see container.cuda)
  rocm: []   # prebuilt thin image over AMD's official rocm/vllm serving base — zero install steps (see container.rocm)

  cpu:
    - "test -d {src}/.git || git clone -b {ref} --depth 1 {repo}.git {src}"
    # the pinned cpu.txt requests torch==2.14.0+cpu, which only the cpu repack
    # index serves (default PyPI has no +cpu wheel); preinstall it first so the
    # -r cpu.txt row is satisfiable (issue #1241, #1544). torch_backend renders to 'cpu'.
    # cpu.txt also asks bare 'torchvision'/'torchaudio' (no +cpu suffix) — resolving
    # them from default PyPI installs _C built against the non-cpu torch ABI, so
    # torchvision::nms/SGD ops never register and 'vllm --version' dies with
    # 'operator torchvision::nms does not exist' at import (issue #1365 run
    # 41345449621 cpu). Preinstall the ABI-matched +cpu wheels from the SAME index.
    # torchcodec (video decoding backend, `>= 0.14` in cpu.txt) has the same class of
    # bug: the default-PyPI wheel fails `torch.ops.load_library(libtorchcodec_image.so)`
    # against the preinstalled +cpu torch with the generic "Could not load this library"
    # (issue #1365 run 41355299891 cpu) — pull it from the same index too.
    # NB: this preinstall pin MUST track the sha's own cpu.txt torch pin (bumped 2.13→2.14
    # at v0.33.0 3a4d82f5). A lag here re-opens #1544: step 2 `-r cpu.txt` wants the sha's
    # newer torch, which default PyPI cannot satisfy (no +cpu wheel) → 'unsatisfiable'.
    - "uv pip install --system --break-system-packages torch==2.14.0 torchvision torchaudio torchcodec --index-url https://download.pytorch.org/whl/{torch_backend}"
    - "uv pip install --system --break-system-packages -r {src}/requirements/build/cpu.txt --index-strategy unsafe-best-match"
    # vendored Rust frontend (vllm-rs): build_rust.sh precompiles the artifacts so -e . skips cargo
    - "cd {src} && bash tools/build_rust.sh"
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
  # Build-strategy (owner 2026-11-08): each vllm GPU cell is a THIN image over vLLM's official
  # prebuilt serving base for that backend — `prebuilt: true` runs ZERO install steps, so the
  # Dockerfile is only `FROM <official-image>` + the llgenie entrypoint wrap (base as-is, trimmed).
  # No source compile, no wheel-install chain, no poetry. The served version is the base's baked vllm.
  #  - rocm: FROM docker.io/rocm/vllm:<AMD-tag>   (issue #1558 / PR #2274)
  #  - cuda: FROM docker.io/vllm/vllm-openai:v0.33.0  (issue #2386 / PR #2429, supersedes #937/#615 for cuda)
  #  - cpu:  source-compiled (remains; no prebuilt cpu serving image today)
  cuda:
    # vLLM's official CUDA serving image, pinned to our vllm ref (v0.33.0). prebuilt: true runs
    # zero install steps; the image ships the baked vllm + CUDA runtime, and `detect` probes it
    # via `from vllm import __version__`. Entrypoint serves (see launch below).
    base: docker.io/vllm/vllm-openai:v0.33.0
    prebuilt: true
    binary: "vllm"
    binary_flags: ["--version"]
  rocm:
    # AMD's official prebuilt rocm/vllm serving base (issue #1558 / PR #2274). prebuilt: true runs
    # zero install steps; the image ships the baked vllm + ROCm runtime, and `detect` probes it via
    # `from vllm import __version__`. Entrypoint serves (see launch below).
    base: docker.io/rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0
    prebuilt: true
    binary: "vllm"
    binary_flags: ["--version"]
  cpu:
    apt: [python3-dev, libnuma-dev]
upstream_watch: [pyproject.toml, requirements/cuda.txt, requirements/rocm.txt, requirements/cpu.txt, docs/getting_started/installation/gpu.md, docs/getting_started/installation/cpu.md, docker/Dockerfile.rocm_base]
---

# vLLM

The GPU cells (cuda, rocm) are THIN images over vLLM's official prebuilt serving base for that
backend (see `container` above): the Dockerfile is `FROM <official-image>` + the llgenie entrypoint
wrap, `prebuilt: true` runs zero install steps, and the served version is the base's baked vllm.
The cpu cell compiles the pinned sha on the shared devel base into the engine image's own Python
(`uv pip install --no-build-isolation -e .`; the container is the isolation, nothing is installed
on the host).

## Hardware parameters

| Backend | Selection | Notes |
|---|---|---|
| cuda | prebuilt: `FROM docker.io/vllm/vllm-openai:v0.33.0` (zero install) | compute capability >= 7.5, fat arch list `75;80;86;89;90;120`; the official CUDA serving image ships vllm + CUDA runtime |
| rocm | prebuilt: `FROM docker.io/rocm/vllm:<AMD-tag>` (zero install) | gfx90a/942/950, RDNA3 gfx1100/1101, RDNA4 gfx1200/1201, Ryzen AI gfx1150/1151; AMD's official rocm/vllm image ships the ROCm runtime |
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
