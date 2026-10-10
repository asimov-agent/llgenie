---
name: engine-llama-cpp-laurentzuijdwijk
description: "Use when building or launching the LaurentZuijdwijk llama.cpp fork (Vulkan on AMD Strix Halo, adaptive speculative decoding via --spec-draft-adaptive)."
engine: "llama.cpp (LaurentZuijdwijk fork)"
id: llama.cpp-laurentzuijdwijk
repo: https://github.com/agentionai/llama.cpp
ref: perf/strix-vulkan
ref_kind: branch
pinned: 3c75be02f45081987e1b4baafd5aa4c5af245de9
verified: "2026-10-05"
license: MIT
servable: true
backends: [vulkan, rocm, cuda, cpu]
os: [linux]
formats: [gguf]
quants: [F32, F16, BF16, Q8_0, Q6_K, Q5_K, Q5_0, Q4_K, Q4_0, Q3_K, Q2_K, Q2_0, IQ4_XS, IQ3_S, IQ2_XS, MXFP4]
src_dir: "{server_root}/laurentzuijdwijk-llama.cpp"
build_dir: "{src}/build-{backend}"
requires:
  min_mesa_radv: "25.3"
prereqs:
  common: [git, cmake, g++]
  vulkan: [glslc, vulkaninfo]
  rocm: [hipconfig]
  cuda: [nvcc]
cmake_flags:
  common: "-DGGML_NATIVE=OFF"
  vulkan: "-DGGML_VULKAN=ON -DGGML_CUDA=OFF -DGGML_METAL=OFF"
  rocm: "-DGGML_HIP=ON -DGGML_CUDA=OFF"
  cuda: "-DGGML_CUDA=ON -DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined"
  cpu: "-DGGML_CUDA=OFF -DGGML_METAL=OFF"
hw_flags:
  cuda:
    cuda_arch: "'-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}'"
  rocm:
    gpu_targets: "'-DGPU_TARGETS={gpu_targets}'"
env:
  rocm:
    HIPCXX: "$(hipconfig -l)/clang"
    HIP_PATH: "$(hipconfig -R)"
install:
  common:
    - "test -d {src}/.git || git clone -b {ref} {repo}.git {src}"
    - "git config --global --add safe.directory {src}"
    - "git -C {src} fetch origin {ref}"
    - "git -C {src} checkout -B {ref} {checkout}"
    - "cmake -S {src} -B {build} -DCMAKE_BUILD_TYPE=Release {cmake_flags}"
    - "cmake --build {build} --config Release -j{jobs} --target llama-server"
    # build-time check: no GPU driver inside a docker build, so the cuda binary is
    # loaded against the toolkit's libcuda stub (the real driver comes from the
    # host at run time via the nvidia CDI device)
    - "LD_LIBRARY_PATH=${{LD_LIBRARY_PATH:-}}:/usr/local/cuda/lib64/stubs {binary} --help > /dev/null"
binary: "{build}/bin/llama-server"
detect: "{binary} --version"
launch: "{binary} -m {model} --host {host} --port {port} --alias {alias} --jinja"
health: "GET /health"
alias_mode: flag
container:                       # compile on the devel base, run on the slim runtime base
  vulkan:
    runtime: true
    runtime_copy: ["{build}/bin"]
  rocm:
    runtime: true
    runtime_copy: ["{build}/bin"]
  cuda:
    runtime: true
    runtime_copy: ["{build}/bin"]
  cpu:
    runtime: true
    runtime_copy: ["{build}/bin"]
upstream_watch: [CMakeLists.txt, common/arg.cpp, ggml/src/ggml-vulkan/CMakeLists.txt, ggml/src/ggml-hip/CMakeLists.txt, docs/build.md, README.md, PROGRESS.md]
---

# llama.cpp — LaurentZuijdwijk fork

Its headline target is **AMD Strix Halo** (Radeon 8060S, `gfx1151`) over **Vulkan on
stock Mesa RADV**, so no ROCm install is needed. The work lives on branch
`perf/strix-vulkan`. The fork's `main` carries the adaptive
spec flags but not the Strix tuning.

## Hardware parameters

- Vulkan is the recommended backend on Strix Halo. It needs **Mesa RADV >= 25.3** for the
  LDS-stride fix: check `vulkaninfo --summary` (driverInfo). Older RADV builds
  work but lose the fix.
- ROCm/CUDA/CPU build like upstream (`GPU_TARGETS` from `rocminfo`,
  `CMAKE_CUDA_ARCHITECTURES` from `nvidia-smi`).

## Fork-only flags

`--spec-draft-adaptive` (env `LLAMA_ARG_SPEC_DRAFT_ADAPTIVE`) and `--spec-draft-n-min`.
The recommended combination is `--spec-type draft-mtp --spec-draft-adaptive --spec-draft-n-min 3`,
but only for a model with an MTP head. It is **not** in the default launch: CI showed that a non-MTP
model then fails with `failed to create MTP context`. The serving tuner (#91) adds it when the
GGUF has `nextn_layers > 0`.
The legacy `--draft-max`/`--draft-min` flags were removed.
