---
name: engine-tensorfold
description: "Use when installing TensorFold (MLX on Apple Silicon, or CUDA sm_89+ in the NVIDIA PyTorch container) and serving `tensorfold serve` as llm-local with MTP/DFlash2 drafting."
engine: "TensorFold"
id: tensorfold
repo: https://github.com/ashhart/TensorFold
ref: v1.1.8
ref_kind: tag
version: v1.1.8
pinned: 812fb0404b1856df29dcb4a285d25dddf469288d
verified: "2026-10-28"
license: Apache-2.0
servable: true
backends: [metal, cuda]
os: [darwin, linux]
formats: [mlx-safetensors, nvfp4, fp8, exl3]
requires:
  min_compute_cap:
    cuda: "8.9"
prereqs:
  # the release-archive install calls curl/tar only — uv went away with the pip install
  common: []
  cuda: [nvidia-smi, nvcc]
install:
  metal:
    - "mkdir -p {prefix}/{version}"
    - "curl -fsSL -o {prefix}/tensorfold-{version}-macos-arm64.tar.gz {repo}/releases/download/v{version}/tensorfold-{version}-macos-arm64.tar.gz"
    - "curl -fsSL -o {prefix}/tensorfold-{version}-macos-arm64.tar.gz.sha256 {repo}/releases/download/v{version}/tensorfold-{version}-macos-arm64.tar.gz.sha256"
    - "cd {prefix} && shasum -a 256 -c tensorfold-{version}-macos-arm64.tar.gz.sha256"
    - "tar -xzf {prefix}/tensorfold-{version}-macos-arm64.tar.gz -C {prefix}/{version} --strip-components=1"
    - "exe=$(find {prefix}/{version}/bin -maxdepth 1 -type f -perm -111); set -- $exe; ln -sfn \"$1\" {prefix}/{version}/bin/{id}"
    - "ln -sfn {prefix}/{version} {prefix}/current"
  cuda:
    - "mkdir -p {prefix}/{version}"
    - "curl -fsSL -o {prefix}/tensorfold-{version}-linux-x86_64.tar.gz {repo}/releases/download/v{version}/tensorfold-{version}-linux-x86_64.tar.gz"
    - "curl -fsSL -o {prefix}/tensorfold-{version}-linux-x86_64.tar.gz.sha256 {repo}/releases/download/v{version}/tensorfold-{version}-linux-x86_64.tar.gz.sha256"
    - "cd {prefix} && sha256sum -c tensorfold-{version}-linux-x86_64.tar.gz.sha256"
    - "tar -xzf {prefix}/tensorfold-{version}-linux-x86_64.tar.gz -C {prefix}/{version} --strip-components=1"
    - "exe=$(find {prefix}/{version}/bin -maxdepth 1 -type f -perm -111); set -- $exe; ln -sfn \"$1\" {prefix}/{version}/bin/{id}"
    - "ln -sfn {prefix}/{version} {prefix}/current"
binary: "{prefix}/current/bin/{id}"
binary_flags: ["--help", "--version"]   # the archive binary answers both (its --version is the installed release)
detect: "{binary} --version"
launch:
  common: "{binary} serve {model} --host {host} --port {port} --name {alias}"
  # Metal: a {context}-token window (LLGENIE_CONTEXT, default 65536 = Hermes Agent's 64K
  # tool-use floor; 0 leaves the flag out so TensorFold sizes it to its budget).
  # 65536 fits only with the full Mac budget below.
  metal: "{context_flag}"
env:
  metal:
    # the whole Mac's RAM; TensorFold caps it at the GPU's recommended working set
    # (37.4 GiB on a 48 GB M5 Pro) instead of its default 70% (33.6 GiB, a 29,696 window)
    TENSORFOLD_MEMORY_LIMIT_GB: "{ram_gib}"
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

On Metal llgenie adds `--context {context}` (default 65536, the 64K Hermes Agent needs
for tool use; `LLGENIE_CONTEXT` overrides, `0` leaves the flag out so TensorFold sizes the
window to its budget; TensorFold's own `--context 0` would mean unlimited) and sets
`TENSORFOLD_MEMORY_LIMIT_GB` to the Mac's RAM, which TensorFold caps at the GPU's
recommended working set. Its default budget is 70% of RAM: on a 48 GB Mac that is
33.6 GiB and a 29,696-token window; the working set (37.4 GiB) serves Qwen3.8-27B-MLX-6bit
with a 65,536 window (measured on an M5 Pro). A Mac whose budget cannot hold 65,536 tokens
gets TensorFold's refusal ("a 65,536-token context window does not fit ... the most one
request can use is N tokens"); `LLGENIE_CONTEXT=0` then serves the window it affords, below
Hermes Agent's 64K floor. `--kv-dtype` is CUDA-only.
