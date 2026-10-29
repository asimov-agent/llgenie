---
name: engine-mlx
description: "Use when building the MLX + mlx-lm engine image (CUDA via mlx[cudaNN] or CPU; Metal natively on Apple Silicon) and serving mlx_lm.server as llm-local."
engine: "MLX"
id: mlx
repo: https://github.com/ml-explore/mlx-lm
ref: v0.32.2
ref_kind: tag
version: v0.32.2
pinned: 93e6d4a6447b3080861985947f0820e76fcb957d
verified: "2026-10-19"
license: MIT
servable: true
backends: [metal, cuda, cpu]
os: [darwin, linux]
formats: [mlx-safetensors]
requires:
  min_compute_cap:
    cuda: "7.5"
  min_cuda:
    cuda: "12.0"
prereqs:
  common: [uv]
  cuda: [nvidia-smi]
install:
  metal:
    - "uv tool install --force mlx-lm=={version}"
  cuda:
    # mlx's C++ core from source (upstream's `mlx[cudaNN]` is a wheel), then mlx-lm from
    # its own tree: no PyPI wheel of either package in the image (issue #615).
    # mlx core pin = tag v0.32.2 = the version mlx-lm {version} pins; setuptools-scm is what
    # writes mlx-lm/_version.py under --no-build-isolation (without it the CLI imports fail).
    - "test -d {prefix}/mlx/.git || git clone https://github.com/ml-explore/mlx.git {prefix}/mlx"
    - "git -C {prefix}/mlx fetch -q origin v0.32.2 && git -C {prefix}/mlx checkout -q 1f8e74e3f12f31365464a6867c6579f0e9b29d85"
    # setup.py builds its own CUDA fat arch list (75,80,90,100,120a,121a) and loads the CUDA
    # libs from the python packages it pulls; BLAS is required by mlx's CMakeLists.txt:326.
    - "uv pip install --system --break-system-packages setuptools wheel typing_extensions setuptools-scm"
    # no GPU in the build image, so the SASS list is explicit (cmake_flags below): mlx's
    # backend/cuda/CMakeLists.txt runs __nvcc_device_query otherwise and fails.
    - "CMAKE_ARGS='{cmake_flags}' uv pip install --system --break-system-packages --no-cache --no-build-isolation {prefix}/mlx"
    - "test -d {src}/.git || git clone {repo}.git {src}"
    - "git -C {src} fetch -q origin {ref} && git -C {src} checkout -q {pinned}"
    - "uv pip install --system --break-system-packages --no-cache --no-build-isolation {src}"
  cpu:
    - "test -d {prefix}/mlx/.git || git clone https://github.com/ml-explore/mlx.git {prefix}/mlx"
    - "git -C {prefix}/mlx fetch -q origin v0.32.2 && git -C {prefix}/mlx checkout -q 1f8e74e3f12f31365464a6867c6579f0e9b29d85"
    - "uv pip install --system --break-system-packages setuptools wheel typing_extensions setuptools-scm"
    - "CMAKE_ARGS='-DMLX_BUILD_METAL=OFF' uv pip install --system --break-system-packages --no-cache --no-build-isolation {prefix}/mlx"
    - "test -d {src}/.git || git clone {repo}.git {src}"
    - "git -C {src} fetch -q origin {ref} && git -C {src} checkout -q {pinned}"
    - "uv pip install --system --break-system-packages --no-cache --no-build-isolation {src}"
cmake_flags:
  cuda: "-DMLX_BUILD_CUDA=ON -DMLX_BUILD_METAL=OFF"
  cpu: "-DMLX_BUILD_METAL=OFF"
hw_flags:
  cuda:
    cuda_arch: "-DMLX_CUDA_ARCHITECTURES={cuda_arch}"   # mlx's own CMake knob
container:          # both image cells compile mlx's C++ core and mlx-lm from the pinned trees
  cuda:             # (issue #615); BLAS/LAPACK headers are how mlx's CMakeLists finds its
    # deps, python3-dev for the bindings, cuDNN's headers for the CUDA cell's own build
    # (CMake's FindCUDNN.cmake fails without cudnn.h — measured 2026-10-29)
    apt: [libopenblas-dev, liblapacke-dev, python3-dev, libcudnn9-dev-cuda-13]
    cuda_archs: "80;86;89;90;120"   # mlx's CUDA backend is sm_80+; 75 is below its minimum
  cpu:
    apt: [libopenblas-dev, liblapacke-dev, python3-dev]
binary: "mlx_lm.server"
binary_flags: ["--help"]   # mlx_lm.server is argparse: --help prints usage (no --version)
binary_probe:
  cuda: device   # mlx[cuda] import needs the CUDA device, so --help cannot answer on a GPU-less runner
  cpu: help      # mlx_lm.server is argparse: --help/-h only, there is no --version flag
detect:
  metal: "{binary} --help > /dev/null && uv tool list | grep '^mlx-lm '"
  cuda: "{binary} --help > /dev/null 2>&1 || python3 -c 'import importlib.metadata as m; print(\"mlx-lm\", m.version(\"mlx-lm\"), \"mlx\", m.version(\"mlx\"))'"
  cpu: "{binary} --help > /dev/null && python3 -c 'import importlib.metadata as m; print(\"mlx-lm\", m.version(\"mlx-lm\"), \"mlx\", m.version(\"mlx\"))'"
launch: "d=/tmp/llgenie-mlx-{port} && mkdir -p $d && cd $d && ln -sfn {model} llm-local && {binary} --model llm-local --host {host} --port {port}"
health: "GET /health"
alias_mode: any-name
upstream_watch: [pyproject.toml, setup.py, mlx_lm/server.py, mlx_lm/SERVER.md]
---

# MLX (mlx-lm)

The engine name in the registry is MLX. The server comes from **mlx-lm**
(`mlx_lm.server`), which pulls the MLX core for the backend.

## Hardware parameters

| Backend | Install | Notes |
|---|---|---|
| metal | `mlx-lm` (pulls `mlx` with Metal) | Apple Silicon M1+, macOS >= 13 (>= 15 for wired-memory). Large models: `sudo sysctl iogpu.wired_limit_mb=<N>` with model size < N < unified RAM (the user is asked first, because this needs sudo) |
| cuda | `mlx[cuda{cuda_major}]` (cuda12 or cuda13 from the detected toolkit) | Linux, driver >= 550.54.14, compute capability >= 7.5 |
| cpu | `mlx[cpu]` | Linux |

Unified RAM bounds model + KV. Use `--max-kv-size`, plus `--kv-bits 4` where available.

## Serving as llm-local

mlx_lm.server has **no alias flag**, and it resolves symlinks, so `/v1/models` always shows the
real model path (CI proved that symlinking the model dir as `llm-local` does not change it).
A request without `model` gets the loaded model, but any other name is loaded as a
path or HF repo (`"model": "llm-local"` -> 404 from huggingface.co, CI #98). So the launch
line serves from `/tmp/llgenie-mlx-<port>` with `llm-local` symlinked to the model and
`--model llm-local`: requests for `llm-local` then hit the loaded model, while
`/v1/models` still lists the resolved path (`alias_mode: any-name`). Needs a local model dir. Routes: `/v1/models`, `/v1/chat/completions`,
`/v1/completions`, `/health`. Speculative decoding: `--draft-model X --num-draft-tokens N`.
The server has no auth, so bind 127.0.0.1 only. Models: MLX safetensors (mlx-community), not GGUF.
