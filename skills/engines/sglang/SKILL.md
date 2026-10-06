---
name: engine-sglang
description: "Use when building the SGLang engine image (CUDA 13 wheels; AMD source build) and serving as llm-local, including DFlash speculative decoding."
engine: "SGLang"
id: sglang
repo: https://github.com/sgl-project/sglang
ref: v0.5.21
ref_kind: tag
version: v0.5.21
pinned: e00930c5489053f26d86b179cee0d087f846acbb
verified: "2026-10-05"
license: Apache-2.0
servable: true
backends: [cuda, rocm]
os: [linux]
formats: [safetensors, awq, gptq, fp8, gguf]
requires:
  min_compute_cap:
    cuda: "7.5"
  min_cuda:
    cuda: "13.0"
prereqs:
  common: [uv]
  cuda: [nvidia-smi, nvcc]
  rocm: [rocminfo, hipconfig, git]
install:
  cuda:
    - "uv pip install --system --break-system-packages --prerelease=allow sglang=={version}"
  rocm:
    - "test -d {src}/.git || git clone -b v{version} --depth 1 {repo}.git {src}"
    # same steps as upstream docker/rocm.Dockerfile (CI #98: the generic
    # pyproject pulled CUDA-only cuda-tile): AOT kernels via pyproject_rocm.toml
    # for ONE AMDGPU_TARGET (setup_rocm.py accepts gfx942/gfx950/gfx1250 only),
    # then pyproject_other.toml with the srt_hip extras, torch pinned to the base's
    - "cd {src}/python/sglang/kernels/aot && rm -f pyproject.toml && cp pyproject_rocm.toml pyproject.toml && AMDGPU_TARGET=gfx942 python3 setup_rocm.py install"
    # the multimodal Rust extension needs cargo (edition 2024: noble's default 1.75 is too old)
    - "ln -sf /usr/bin/cargo-1.91 /usr/local/bin/cargo && ln -sf /usr/bin/rustc-1.91 /usr/local/bin/rustc"
    - "pip list --format=freeze | grep -E '^(torch|triton)' > /tmp/sglang-constraints.txt"
    - "cd {src} && cp python/pyproject_other.toml python/pyproject.toml && SETUPTOOLS_SCM_PRETEND_VERSION={version} python3 -m pip install --no-cache-dir --no-build-isolation -c /tmp/sglang-constraints.txt -e 'python[srt_hip,diffusion_hip]'"
env:
  cuda:
    CUDA_HOME: "$(dirname $(dirname $(command -v nvcc)))"
  rocm:
    SGLANG_USE_AITER: "1"
binary: "sglang"
detect: "python3 -c 'import sglang; print(sglang.__version__)'"
launch: "{binary} serve --model-path {model} --host {host} --port {port} --served-model-name {alias}"
health: "GET /health"
alias_mode: flag
container:
  cuda:     # official image
    base: "lmsysorg/sglang:v{version}"
    prebuilt: true
  rocm:
    # pinned to the base of sglang's own docker/rocm.Dockerfile (ROCm 7.2.4, torch 2.10):
    # rocm/pytorch:latest moved to a torch whose headers need C++20, while
    # kernels/aot/setup_rocm.py hard-codes -std=c++17 (CI #98)
    base: "rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e"
    apt: [rustc-1.91, cargo-1.91]
upstream_watch: [python/pyproject.toml, python/pyproject_other.toml, python/sglang/cli/serve.py, python/sglang/srt/arg_groups/field_order.py, docker/Dockerfile, docs/get-started/install.md]
---

# SGLang

## Hardware parameters

- **cuda:** the mainline wheels are **CUDA 13** builds (0.5.19 was the last CUDA 12
  release) and need a CUDA-13 capable driver. The FlashInfer default attention kernel
  needs sm75+. If `CUDA_HOME not set` appears, it is derived from `nvcc`.
- **rocm:** no wheel. Build from source at the tag with
  `PYTORCH_ROCM_ARCH={gpu_targets}` (from `rocminfo`), then install `python[all_hip]`.
  Marlin-based quants (awq_marlin, gptq_marlin, gguf) do not work on AMD.

## Launch

`sglang serve --model-path <hf-id|dir> --host 127.0.0.1 --port 11434 --served-model-name llm-local`.
The CLI flags are generated from dataclass fields (`served_model_name` ->
`--served-model-name`). Memory: `--mem-fraction-static`. DFlash drafters:
`--speculative-algorithm DFLASH --speculative-draft-model-path <drafter>
--speculative-num-draft-tokens 8` (see the `dflash2` skill).
