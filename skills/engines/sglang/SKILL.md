---
name: engine-sglang
description: "Use when building the SGLang engine image from source (CUDA and ROCm both compile the pinned sha) and serving as llm-local, including DFlash speculative decoding."
engine: "SGLang"
id: sglang
repo: https://github.com/sgl-project/sglang
ref: v0.5.23
ref_kind: tag
version: v0.5.23
pinned: 7df5dd09bc2f0e7e1509a1f7c2a40dff00ad8a01
verified: "2026-11-02"
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
hw_flags:
  cuda:
    cuda_arch: "'-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}'"
install:
  cuda:
    # PREBUILT (no source compile): the official lmsysorg/sglang:v0.5.23 serving image already
    # contains the engine + its compiled CUDA kernels, so `prebuilt: true` below makes the
    # renderer run ZERO install steps (engine_skills.py: `if prebuilt: steps=[]`).
    # Root cause of the all-fail Oct 31→Nov 1 cell: the earlier source AOT build (issue #938)
    # compiled sglang-kernel from the pinned sha on nvidia/cuda:13.0.2-devel. The single
    # csrc/gemm/fp8_gemm_kernel.cu nvcc pass exceeds 16GiB at EVERY arch set and thread cap
    # (measured: 6-arch list AND a strict single-arch TORCH_CUDA_ARCH_LIST=8.9 both OOM-kill at
    # fp8_gemm_kernel.cu.o, Error 255, under a 16GiB/4-CPU cap) — kernel-size-bound, not knob-fixable.
    # Restoring the prebuilt base is the only OOM-safe path; the #1242 uv/pip bootstrap we added
    # for the devel base is moot here (the prebuilt image ships its own runtime and pip-equivalent).
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
binary_flags: ["--help"]   # the sglang CLI answers --help (no --version); detect proves it
binary_probe:                # argparse-only CLI: the help family must answer, the version
  cuda: help                 # comes from the image's `detect` (the installed distribution's version,
  rocm: help                 # or the pin when that distribution reports 0.0.0 — the ROCm wheel does)
detect: "{binary} --help > /dev/null && python3 -c 'import importlib.metadata as m; v = m.version(\"sglang\"); print(\"sglang\", v if v not in (\"0.0.0\", \"\") else \"{version}\")'"   # the installed distribution, or the PINNED VERSION when it reports 0.0.0 (the ROCm wheel does); a commit sha is not a version (#636)
launch: "{binary} serve --model-path {model} --host {host} --port {port} --served-model-name {alias}"
health: "GET /health"
alias_mode: flag
container:
  cuda:
    # prebuilt official serving image (restore the green Oct 25-30 base): ships the engine
    # + compiled CUDA kernels, so `prebuilt: true` runs no install steps. The source devel
    # build (issue #938) OOMs compiling fp8_gemm_kernel.cu at any arch set / thread cap — see install.
    base: "lmsysorg/sglang:v0.5.23"
    prebuilt: true
    apt: [python3, wget]
  rocm:
    # pinned to the base of sglang's own docker/rocm.Dockerfile (ROCm 7.2.4, torch 2.10):
    # rocm/pytorch:latest moved to a torch whose headers need C++20, while
    # kernels/aot/setup_rocm.py hard-codes -std=c++17 (CI #98)
    base: "rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e"
    apt: [rustc-1.91, cargo-1.91, wget]
upstream_watch: [python/pyproject.toml, python/pyproject_other.toml, python/sglang/cli/serve.py, python/sglang/srt/arg_groups/field_order.py, docker/Dockerfile, docs/get-started/install.md]
---

# SGLang

## Hardware parameters

- **cuda:** source build at the pinned sha (issue #938): torch 2.14.1 preinstalled from the
  cu130 index, then `python[all]` and the AOT CUDA kernels compiled with the fat arch list.
  Needs a CUDA-13 capable driver. The FlashInfer default attention kernel needs sm75+.
  If `CUDA_HOME not set` appears, it is derived from `nvcc`.
- **rocm:** no wheel. Build from source at the tag with
  `PYTORCH_ROCM_ARCH={gpu_targets}` (from `rocminfo`), then install `python[all_hip]`.
  Marlin-based quants (awq_marlin, gptq_marlin, gguf) do not work on AMD.

## Launch

`sglang serve --model-path <hf-id|dir> --host 127.0.0.1 --port 11434 --served-model-name llm-local`.
The CLI flags are generated from dataclass fields (`served_model_name` ->
`--served-model-name`). Memory: `--mem-fraction-static`. DFlash drafters:
`--speculative-algorithm DFLASH --speculative-draft-model-path <drafter>
--speculative-num-draft-tokens 8` (see the `dflash2` skill).
