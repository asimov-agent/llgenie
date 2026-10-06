---
name: engine-tensorfold
description: "Use when installing TensorFold (MLX on Apple Silicon, or CUDA sm_89+ in the NVIDIA PyTorch container) and serving `tensorfold serve` as llm-local with MTP/DFlash2 drafting."
engine: "TensorFold"
id: tensorfold
repo: https://github.com/ashhart/TensorFold
ref: v0.6.5
ref_kind: tag
version: v0.6.5
pinned: 609ca419abecebdc5a059498a613680bd3aa847f
verified: "2026-10-05"
license: Apache-2.0
servable: true
backends: [metal, cuda]
os: [darwin, linux]
formats: [mlx-safetensors, nvfp4, fp8, exl3]
requires:
  min_compute_cap:
    cuda: "8.9"
prereqs:
  common: [uv]
  cuda: [nvidia-smi, nvcc]
install:
  metal:
    - "uv tool install --force 'tensorfold @ git+{repo}.git@v{version}'"
  cuda:
    - "uv pip install --system --break-system-packages torch triton"
    - "uv pip install --system --break-system-packages 'tensorfold @ git+{repo}.git@v{version}'"
binary: "tensorfold"
detect:
  metal: "{binary} --help > /dev/null && uv tool list | grep '^tensorfold '"
  cuda: "{binary} --help > /dev/null && python3 -c 'import importlib.metadata as m; print(m.version(\"tensorfold\"))'"
launch: "{binary} serve {model} --host {host} --port {port} --name {alias}"
health: "GET /v1/models"
alias_mode: flag
container:
  cuda:     # upstream-supported CUDA runtime
    base: "nvcr.io/nvidia/pytorch:26.07-py3"
upstream_watch: [pyproject.toml, README.md, RUNBOOK.md, src/tensorfold/server.py, src/tensorfold/cli.py]
---

# TensorFold

## Hardware parameters

- **metal:** Apple Silicon, Python >= 3.11, MLX >= 0.32.2 (pulled automatically).
  Parallel decode: `--parallel N` (up to 8 on MLX).
- **cuda:** compute capability **>= 8.9** (Ada, Hopper, Blackwell, GB10, RTX 50).
  RTX 30 (8.6) is refused at startup. Upstream supports running inside
  `nvcr.io/nvidia/pytorch:26.07-py3`. Other CUDA bases need torch + triton + nvcc in the image.
  2-rank: `--tp 2 --rank R --master HOST`.
- Drafting: MTP heads built into the checkpoints, plus an optional DFlash2 drafter
  (`--drafter z-lab/Qwen3.8-27B-DFlash2`; `--no-drafts` disables it).

## Launch

`tensorfold serve <model> --host 127.0.0.1 --port 11434 --name llm-local`.
`--name` sets the advertised id. Routes: `/v1/models`, `/v1/chat/completions`,
`/v1/completions`, `/v1/responses`, `/v1/messages`. No documented `/health`,
so readiness is probed with `/v1/models`. Supported families only (Qwen3.8-27B,
Qwen3.8 Flash Next, Nemotron, GLM-5.3-Flash, Gemma 4 26B, DeepSeek-V4-Flash,
Ternary Bonsai 2 27B).
