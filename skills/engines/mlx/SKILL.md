---
name: engine-mlx
description: "Use when building the MLX + mlx-lm engine image (CUDA via mlx[cudaNN] or CPU; Metal natively on Apple Silicon) and serving mlx_lm.server as llm-local."
engine: "MLX"
id: mlx
repo: https://github.com/ml-explore/mlx-lm
ref: v0.32.0
ref_kind: tag
version: v0.32.0
pinned: a9bd8af5c02118882af735cef60705d2efce9fd0
verified: "2026-10-05"
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
    - "uv pip install --system --break-system-packages 'mlx[cuda{cuda_major}]' mlx-lm=={version}"
  cpu:
    - "uv pip install --system --break-system-packages 'mlx[cpu]' mlx-lm=={version}"
binary: "mlx_lm.server"
detect:
  metal: "{binary} --help > /dev/null && uv tool list | grep '^mlx-lm '"
  cuda: "{binary} --help > /dev/null 2>&1 || python3 -c 'import importlib.metadata as m; print(\"mlx-lm\", m.version(\"mlx-lm\"), \"mlx\", m.version(\"mlx\"))'"
  cpu: "python3 -c 'import importlib.metadata as m; print(\"mlx-lm\", m.version(\"mlx-lm\"), \"mlx\", m.version(\"mlx\"))'"
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
