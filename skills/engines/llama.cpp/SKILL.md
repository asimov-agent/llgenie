---
name: engine-llama-cpp
description: "Use when building, installing or launching upstream llama.cpp llama-server (ggml-org) for a CUDA, ROCm, Vulkan, Metal or CPU host."
engine: "llama.cpp"
id: llama.cpp
repo: https://github.com/ggml-org/llama.cpp
ref: master
ref_kind: branch
pinned: 8f9ae20c86ab9d7f092a0c95921f416125907337
verified: "2026-10-05"
license: MIT
servable: true
backends: [cuda, rocm, vulkan, metal, cpu]
os: [linux, darwin]
formats: [gguf]
quants: [F32, F16, BF16, Q8_0, Q6_K, Q5_K, Q5_0, Q5_1, Q4_K, Q4_0, Q4_1, Q3_K, Q2_K, Q2_0, IQ4_XS, IQ4_NL, IQ3_S, IQ3_XXS, IQ2_XS, IQ2_XXS, IQ1_S, IQ1_M, TQ1_0, TQ2_0, MXFP4]
src_dir: "{server_root}/llama.cpp"
build_dir: "{src}/build-{backend}"
prereqs:
  common: [git, cmake, g++]
  cuda: [nvcc]
  rocm: [hipconfig]
  vulkan: [glslc]
  metal: [xcrun]
cmake_flags:
  common: "-DGGML_NATIVE=OFF"
  cuda: "-DGGML_CUDA=ON -DGGML_METAL=OFF -DGGML_SYCL=OFF"
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
    - "{binary} --help > /dev/null"
binary: "{build}/bin/llama-server"
detect: "{binary} --version"
launch: "{binary} -m {model} --host {host} --port {port} --alias {alias} --jinja"
health: "GET /health"
alias_mode: flag
container:                       # official upstream images (ggml-org), pinned by digest; llama-server at /app
  cpu:
    base: "ghcr.io/ggml-org/llama.cpp:server@sha256:559ac229adefe0f7e2d4e32f5222f26927b6bb8ba44b9db08e2544afebf41984"
    prebuilt: true
    binary: /app/llama-server
  cuda:
    base: "ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:ef08b5a98b1170f2b62177be0a4027c88a84043c55afbf190dd18b9e7cdcfebf"
    prebuilt: true
    binary: /app/llama-server
  rocm:
    base: "ghcr.io/ggml-org/llama.cpp:server-rocm@sha256:46583bd112bf2d62881d6aeaae52e59238d61cbf5803296521cdf518548016e6"
    prebuilt: true
    binary: /app/llama-server
  vulkan:
    base: "ghcr.io/ggml-org/llama.cpp:server-vulkan@sha256:431561ee79ee67b3980a02ff47ed9dc19496127643b75671d9789ef693ca57f9"
    prebuilt: true
    binary: /app/llama-server
upstream_watch: [CMakeLists.txt, ggml/CMakeLists.txt, ggml/src/ggml-cuda/CMakeLists.txt, ggml/src/ggml-hip/CMakeLists.txt, docs/build.md, tools/server/README.md, common/arg.cpp]
---

# llama.cpp (upstream)

Stock ggml-org llama.cpp `llama-server`. GGUF only. Loads every standard quant,
including group-64 `Q2_0` (type id 42). It does **not** load the PrismML
`PQ2_0` / `PTQ1_0` group-128 ternary types: use `llama.cpp-prism` for those.

## Hardware parameters (derived, never guessed)

| Backend | Detected from | Build flag |
|---|---|---|
| cuda | `nvidia-smi --query-gpu=compute_cap` (8.9 -> 89) | `-DCMAKE_CUDA_ARCHITECTURES=89` |
| rocm | `rocminfo` agent `gfxNNNN` | `-DGPU_TARGETS=gfx1100` + `HIPCXX`/`HIP_PATH` from `hipconfig` |
| vulkan | `vulkaninfo` + `glslc` present | `-DGGML_VULKAN=ON` |
| metal | Apple Silicon | `-DGGML_METAL=ON` (default on macOS) |
| cpu | fallback | `-DGGML_NATIVE=OFF` (portable; the CI cache reuses binaries across runners) |

When no GPU is visible (CI containers) the CUDA build omits the arch flag and
CMake builds its default arch list. `GGML_NATIVE=OFF` keeps the binary portable.

## Renamed options (checked against `CMakeLists.txt` at the pinned sha)

- `LLAMA_CUBLAS` is a FATAL_ERROR shim and `LLAMA_CUDA` a warning shim. Use `GGML_CUDA`.
- `LLAMA_HIPBLAS` has no shim. Use `GGML_HIP`.
- `AMDGPU_TARGETS` is a legacy alias for `GPU_TARGETS`.
- `GGML_CUDA_FA_ALL_QUANTS` is deprecated. Use `GGML_CUDA_FA_QUANTS=all`.

## Launch

`llama-server -m <gguf> --host 127.0.0.1 --port 11434 --alias llm-local --jinja`.
`GET /health`. OpenAI routes: `/v1/models`, `/v1/chat/completions`,
`/v1/completions`, `/v1/embeddings`, `/v1/responses`. The tuned serving flags
(`-c`, `-ngl`, `-ctk/-ctv`, MTP) come from `scripts/llama_serve.py`
`build_command()` (issue #91).

## Container images

The images use the **official ggml-org server images** as their base (`ghcr.io/ggml-org/llama.cpp:server`,
`server-cuda`, `server-rocm`, `server-vulkan`, pinned by digest), so nothing is compiled.
Upstream builds them fat (all CUDA archs, `GGML_BACKEND_DL` + `GGML_CPU_ALL_VARIANTS`).
Drift sync (#100) bumps the digests together with `pinned`. The compile path above stays for native
builds (`make install` / `build-variant`) and for the forks, which publish no images.

## Verify

`make engine-plan ENGINE=llama.cpp` shows the rendered build for this machine.
CI builds it via `make build-variant TREE=upstream BACKEND=cpu|cuda|metal`.
