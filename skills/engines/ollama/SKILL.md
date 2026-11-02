---
name: engine-ollama
description: "Use when building Ollama from the pinned Go source (upstream's own go build plus its vendored llama.cpp runners) and serving a GGUF as llm-local."
engine: "Ollama"
id: ollama
repo: https://github.com/ollama/ollama
ref: v0.40.13
ref_kind: tag
version: v0.40.13
pinned: 04088e7c9d41cba5d33bafbf788d87a465c79d5b
verified: "2026-11-02"
license: MIT
servable: true
backends: [cuda, rocm, vulkan, metal, cpu]
os: [linux, darwin]
formats: [gguf]
requires:
  min_compute_cap:
    cuda: "5.0"
prereqs:
  common: [git]
  metal: [curl]
hw_flags:
  cuda:
    cuda_arch: "'-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}'"
  rocm:
    gpu_targets: "'-DAMDGPU_TARGETS={gpu_targets}'"
install:
  # Every Linux cell builds the engine from the pinned sha (issue #936): the Go
  # binary with the settings ollama's own release Dockerfile uses, and the
  # llama.cpp runner from the tree ollama vendors (`llama/server`, presets
  # configure GGML per backend; `LLAMA_CPP_VERSION` pins the llama.cpp source the
  # preset FetchContent-clones). The image bases supply go (golang-go), cmake,
  # ninja, gcc and the backend's toolkit; nothing is downloaded prebuilt.
  #
  # `go generate ./...` is deliberately NOT run: at this pin ollama's release
  # Dockerfile build stage is `go mod download` -> `COPY . .` -> `go build`, and
  # the tree's only `//go:generate` directives are the desktop app's UI
  # (`npm --prefix ./app run build`) and `mlx/mlx.go` (darwin-only C bindings) —
  # neither is an input to `go build .` on linux. `OLLAMA_SKIP_*` does not exist
  # at this sha (`grep -rn OLLAMA_SKIP .` -> no match).
  common:
    - "test -d {src}/.git || git clone -b {ref} {repo}.git {src}"
    - "git config --global --add safe.directory {src}"
    - "git -C {src} fetch origin {checkout}"
    - "git -C {src} checkout --detach {checkout}"
    - "cd {src} && mkdir -p {prefix}/{version}/bin && CGO_ENABLED=1 go build -trimpath -buildmode=pie -ldflags '-w -s -X=github.com/ollama/ollama/version.Version={version} -X=github.com/ollama/ollama/server.mode=release' -o {prefix}/{version}/bin/ollama ."
    # the CPU runner every image carries: ollama falls back to it when no GPU
    # backend loads, and the cpu cell serves with it alone
    - "cd {src} && CMAKE_GENERATOR=Ninja cmake -S llama/server --preset cpu && cmake --build {src}/build/llama-server-cpu -- -l {jobs}"
    - "cmake --install {src}/build/llama-server-cpu --prefix {prefix}/{version} --component llama-server --strip"
  cuda:
    # CUDA 13: the shared cuda devel base is nvidia/cuda:13.0.2-devel, so the
    # cuda_v13 preset's runner is the one this toolkit can compile
    - "cd {src} && CMAKE_GENERATOR=Ninja cmake -S llama/server --preset llama_cuda_v13_linux {cmake_flags} && cmake --build {src}/build/llama-server-cuda_v13 -- -l {jobs}"
    - "cmake --install {src}/build/llama-server-cuda_v13 --prefix {prefix}/{version} --component llama-server --strip"
  rocm:
    # upstream's rocm_v7_2 preset cache variables, but the shared rocm base is
    # ROCm 7.0 and the runner dir must say what it was built against
    - "cd {src} && CMAKE_GENERATOR=Ninja cmake -S llama/server -B {src}/build/llama-server-rocm -DGGML_HIP=ON -DCMAKE_HIP_PLATFORM=amd -DOLLAMA_RUNNER_DIR=rocm_v7_0 -DOLLAMA_GPU_BACKEND=hip {cmake_flags} && cmake --build {src}/build/llama-server-rocm -- -l {jobs}"
    - "cmake --install {src}/build/llama-server-rocm --prefix {prefix}/{version} --component llama-server --strip"
  vulkan:
    - "cd {src} && CMAKE_GENERATOR=Ninja cmake -S llama/server --preset vulkan && cmake --build {src}/build/llama-server-vulkan -- -l {jobs}"
    - "cmake --install {src}/build/llama-server-vulkan --prefix {prefix}/{version} --component llama-server --strip"
  metal:
    # macOS has no container: the darwin release build is upstream's own binary
    - "curl -fsSL -o {prefix}/sha256sum.txt https://github.com/ollama/ollama/releases/download/v{version}/sha256sum.txt"
    - "curl -fsSL -o {prefix}/ollama-darwin.tgz https://github.com/ollama/ollama/releases/download/v{version}/ollama-darwin.tgz"
    - "cd {prefix} && grep ' ./ollama-darwin.tgz$' sha256sum.txt | sed 's# ./# #' | shasum -a 256 -c -"
    - "mkdir -p {prefix}/{version}/bin && tar -xzf {prefix}/ollama-darwin.tgz -C {prefix}/{version}/bin"
binary: "{prefix}/{version}/bin/ollama"   # standard bin/lib layout: the runners sit in {prefix}/{version}/lib/ollama
binary_flags: ["--version", "--help"]   # ollama answers --version (detect) and --help (usage)
env:
  common:
    OLLAMA_HOST: "{host}:{port}"
    OLLAMA_MODELS: "{prefix}/models"
    OLLAMA_FLASH_ATTENTION: "1"
    OLLAMA_KV_CACHE_TYPE: "q8_0"
  rocm:
    HSA_OVERRIDE_GFX_VERSION: ""
detect: "{binary} --version"
launch: "{binary} serve"
post_launch: "printf 'FROM %s\\n' {model} > {prefix}/Modelfile && {binary} create {alias} -f {prefix}/Modelfile"
health: "GET /api/version"
alias_mode: create
container:                       # compiled from the pinned sha in every backend (issue #936):
                                 # shared devel base for the build, binary + runners onto the slim
                                 # runtime base; golang-go is the only extra build tool
  cuda:
    runtime: true
    runtime_copy: ["{prefix}/{version}/bin", "{prefix}/{version}/lib"]
    apt: [golang-go]
  rocm:
    runtime: true
    runtime_copy: ["{prefix}/{version}/bin", "{prefix}/{version}/lib"]
    apt: [golang-go]
  vulkan:
    runtime: true
    runtime_copy: ["{prefix}/{version}/bin", "{prefix}/{version}/lib"]
    apt: [golang-go]
  cpu:
    runtime: true
    runtime_copy: ["{prefix}/{version}/bin", "{prefix}/{version}/lib"]
    apt: [golang-go]
upstream_watch: [Dockerfile, scripts/build_linux.sh, scripts/env.sh, go.mod, LLAMA_CPP_VERSION, CMakePresets.json, llama/server/CMakePresets.json, docs/gpu.mdx, docs/faq.mdx, docs/openai.mdx]
---

# Ollama

Built from the **Go source at the pinned tag** (`f067033f…` = `v0.40.12`), the way Ollama's own
release builds it: `CGO_ENABLED=1 go build -trimpath -buildmode=pie` with the version/mode
`-ldflags`, plus the llama.cpp runner Ollama vendors in the same tree (`llama/server`, a CMake
preset per GPU backend, `LLAMA_CPP_VERSION` pinning the llama.cpp source). Nothing is pulled
prebuilt: no `ollama/ollama` image, no `ollama-linux-<arch>.tar.zst` from the release.

The image is multi-stage: the build happens on the shared devel base for the backend
(`llgenie/base-<backend>`, which carries gcc/cmake/ninja and the backend's toolkit, plus
`golang-go`), and only `{prefix}/{version}/bin` (the binary) and `{prefix}/{version}/lib` (the
runners) are copied onto the slim runtime base. `ollama` finds its runners as
`<exe-dir>/../lib/ollama`, which is exactly that layout.

## Hardware parameters

| Backend | Runner built | Notes |
|---|---|---|
| cuda | `llama_cuda_v13_linux` → `lib/ollama/cuda_v13`, archs `75;80;86;89;90;120` | Needs an NVIDIA driver new enough for the **CUDA 13** runtime (the shared cuda devel base is `nvidia/cuda:13.0.2-devel`); upstream's tarball also carried a `cuda_v12` runner for older drivers, which this cell does not build |
| rocm | `GGML_HIP=ON` with `AMDGPU_TARGETS` from the shared fat list → `lib/ollama/rocm_v7_0` | Built on the shared rocm base (ROCm 7.0), so the runner dir says `rocm_v7_0`. Other RDNA cards: set `HSA_OVERRIDE_GFX_VERSION` (e.g. gfx1034 -> `10.3.0`) |
| vulkan | `vulkan` preset → `lib/ollama/vulkan` | Intel/AMD fallback. VRAM scheduling needs `cap_perfmon` |
| cpu | `cpu` preset (all CPU variants) → `lib/ollama/` | every image also carries this runner, because Ollama falls back to it when no GPU backend loads |
| metal | — | macOS, native: the `ollama-darwin.tgz` release binary (no container on Metal) |

The env is derived from the card at launch: `OLLAMA_FLASH_ATTENTION=1` and
`OLLAMA_KV_CACHE_TYPE=q8_0` shrink the KV cache. Use `q4_0` on <= 8 GB cards.

## Serving as llm-local

1. `OLLAMA_HOST=127.0.0.1:11434 ollama serve` (the native port is already 11434).
2. Write a Modelfile with the line `FROM /abs/model.gguf` (optionally `PARAMETER num_ctx N`).
3. `ollama create llm-local -f Modelfile`.

`/v1/models` lists it as `llm-local:latest`. Requests with `"model": "llm-local"`
resolve to it, because Ollama adds `:latest` itself. Verified on an RTX 4090 Laptop: the
log shows `library=CUDA compute=8.9`, and the 0.5B Qwen answers "hi".

OpenAI routes: `/v1/chat/completions`, `/v1/completions`, `/v1/models`,
`/v1/embeddings`, `/v1/responses`. Readiness: `GET /api/version`.
