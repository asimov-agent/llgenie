---
name: engine-strata
description: "Use when installing Strata (Qwen3.8-Flash-Next 125B MoE across GPU/RAM/SSD; NVIDIA r580+ or AMD RDNA) and serving it as llm-local."
engine: "Strata"
id: strata
repo: https://github.com/Niko1221/Strata
ref: v0.1.39
ref_kind: tag
version: v0.1.39
pinned: 6f32ec070f23ced9f50e704d854d775da52591ab
verified: "2026-10-05"
license: MIT
servable: true
backends: [cuda, rocm]
os: [linux]
formats: [gguf, strata-pack]
models: ["Qwen3.8-Flash-Next 125B"]
requires:
  min_compute_cap:
    cuda: "7.5"
  gpu_targets:
    rocm: [gfx1030, gfx1100, gfx1101, gfx1200, gfx1201]
prereqs:
  common: [git, python3]
  cuda: [nvidia-smi]
  rocm: [rocminfo]
install:
  common:
    - "test -d {src}/.git || git clone -b v{version} --depth 1 {repo}.git {src}"
    - "git -C {src} fetch --depth 1 origin tag v{version} && git -C {src} checkout -q v{version}"
    - "cd {src} && ./setup.sh --setup --yes --port {port} --data-dir {prefix}/data"
binary: "{src}/serve/server.py"
detect: "test -x {src}/.venv/bin/python && ls {src}/run-*.sh"
launch: "cd {src} && ./setup.sh --port {port}"
pre_launch: "{src}/.venv/bin/python -c \"import json,glob; p=sorted(glob.glob('{src}/strata-*.json'))[0]; d=json.load(open(p)); d['aliases']=sorted(set(d.get('aliases',[])+['{alias}'])); d['host']='{host}'; json.dump(d,open(p,'w'),indent=2)\""
health: "GET /health"
alias_mode: config
container: false   # setup.sh is an interactive installer that manages its own engine/data dirs
upstream_watch: [setup.sh, setup.py, serve/server.py, docs/INSTALL.md, docs/DETAILS.md, Dockerfile]
---

# Strata

A llama.cpp-derived C++ engine plus a Python server. It serves **only Qwen3.8-Flash-Next
(125B MoE)** and streams experts across GPU, RAM and SSD.

## Hardware parameters

- **cuda:** NVIDIA RTX 20-50 with >= 12 GB, driver r580+ / CUDA 13. `setup.sh`
  downloads a ready-made engine for RTX20-50. Otherwise it compiles one
  (build-essential + CUDA toolkit, 20-40 min). The Docker build arg is
  `CUDA_ARCHITECTURES={cuda_arch}` (default `86;89;120;80`).
- **rocm:** RX 6800/6900 (gfx1030), 7900 XT/XTX (gfx1100), 7800/7700 (gfx1101),
  9060 XT (gfx1200), 9070 (gfx1201), R9700. The engine is compiled for the card. ROCm
  wheels go into its `.venv`, so no system ROCm install is needed.
- **RAM/SSD tiers (derived from free RAM):** `--resident-budget-gib N`,
  `--mmap-experts` / `--low-ram on`, `--vram-reserve-mib`, `--kv-resident`, `--kv q4_0|int8|k8v4`.
  `setup.sh` picks these from the detected RAM and VRAM.
- Disk: about 80 GB (model) + 6 GB (MTP layer). Use an NVMe SSD.

## Serving as llm-local

The server accepts any model name. The skill also adds `"aliases": ["llm-local"]`
to `strata-<model>.json` so `/v1/models` lists it (supported since 0.1.32). Port: `--port 11434`.
Routes: `/v1/chat/completions`, `/v1/messages`, `/v1/responses`, `/v1/models`, `/health`.
