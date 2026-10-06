---
name: engine-llama-cpp-prism
description: "Use when building or launching the PrismML llama.cpp fork (prism branch), required for Ternary Bonsai PQ2_0/PTQ1_0 GGUFs that stock llama.cpp rejects."
engine: "llama.cpp (PrismML fork)"
id: llama.cpp-prism
repo: https://github.com/PrismML-Eng/llama.cpp
ref: prism
ref_kind: branch
pinned: 2459f68b5c0eb26261fd5a81682004b93cd645ba
verified: "2026-10-05"
license: MIT
servable: true
backends: [cuda, rocm, vulkan, metal, cpu]
os: [linux, darwin]
formats: [gguf]
quants: [PQ2_0, PTQ1_0, Q2_0, F32, F16, BF16, Q8_0, Q6_K, Q5_K, Q5_0, Q5_1, Q4_K, Q4_0, Q4_1, Q3_K, Q2_K, IQ4_XS, IQ4_NL, IQ3_S, IQ3_XXS, IQ2_XS, IQ2_XXS, IQ1_S, IQ1_M, TQ1_0, TQ2_0, MXFP4]
src_dir: "{server_root}/prism-llama.cpp"
build_dir: "{src}/build-{backend}"
prereqs:
  common: [git, cmake, g++]
  cuda: [nvcc]
  rocm: [hipconfig]
  vulkan: [glslc]
  metal: [xcrun]
cmake_flags:
  common: "-DGGML_NATIVE=OFF"
  cuda: "-DGGML_CUDA=ON -DGGML_METAL=OFF -DGGML_SYCL=OFF -DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined"
  rocm: "-DGGML_HIP=ON -DGGML_METAL=OFF -DGGML_CUDA=OFF"
  vulkan: "-DGGML_VULKAN=ON -DGGML_METAL=OFF -DGGML_CUDA=OFF"
  metal: "-DGGML_METAL=ON -DGGML_CUDA=OFF -DGGML_SYCL=OFF"
  cpu: "-DGGML_METAL=OFF -DGGML_CUDA=OFF -DGGML_SYCL=OFF"
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
  cuda:
    runtime: true
    runtime_copy: ["{build}/bin"]
  rocm:
    runtime: true
    runtime_copy: ["{build}/bin"]
  vulkan:
    runtime: true
    runtime_copy: ["{build}/bin"]
  cpu:
    runtime: true
    runtime_copy: ["{build}/bin"]
upstream_watch: [CMakeLists.txt, ggml/CMakeLists.txt, ggml/include/ggml.h, ggml/src/ggml.c, ggml/src/ggml-common.h, ggml/src/ggml-cuda/CMakeLists.txt, ggml/src/ggml-hip/CMakeLists.txt, common/speculative.cpp, tools/server/README.md]
---

# llama.cpp — PrismML fork

The `prism` branch (developed as `prism-v7`) of PrismML-Eng/llama.cpp. It builds
the same way as upstream and serves the same `/v1` routes. It adds two
ggml types (in `ggml/include/ggml.h`):

- `GGML_TYPE_PQ2_0 = 142`: group-128 Q2.0. The preferred Ternary Bonsai 2 file (`*-PQ2_0.gguf`).
- `GGML_TYPE_PTQ1_0 = 143`: Prism group-128 ternary (`*-PTQ1_0.gguf`).

Group-64 `Q2_0` (id 42, the `*-Q2_0_g64.gguf` files) also loads here and on
upstream. Legacy group-128 files stored as id 42 need the frozen `prism-v5` branch.
Do not track `prism-v6`, which is a stale snapshot.

## Hardware parameters

Same as `llama.cpp`: CUDA arch from `nvidia-smi compute_cap`, ROCm `GPU_TARGETS`
from `rocminfo`, Metal on Apple Silicon, portable CPU (`GGML_NATIVE=OFF`).

## Fork-only launch flags

`--spec-type draft-dspark` / `--spec-type draft-dflash` for DSpark/DFlash
drafters (`common/speculative.cpp`).

## Verify

`make build-variant TREE=prism BACKEND=cuda` (CI matrix), then
`make test-serve-variant TREE=prism BACKEND=cuda`.
