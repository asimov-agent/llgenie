---
name: engine-exllamav3-rocm
description: "Use when installing the CarouselAether ExLlamaV3 ROCm fork on AMD RDNA3/3.5/4 (ROCm >= 7.2.4) and serving its bundled exl3_server as llm-local."
engine: "ExLlamaV3 (ROCm fork)"
id: exllamav3-rocm
repo: https://github.com/CarouselAether/rocm_exl3
ref: main
ref_kind: branch
pinned: 5226de53a23fd5248658559b0eb876f6fc0c249a
verified: "2026-10-05"
license: MIT
servable: true
backends: [rocm]
os: [linux]
formats: [exl3, safetensors]
requires:
  gpu_targets:
    rocm: [gfx1100, gfx1101, gfx1102, gfx1150, gfx1151, gfx1200, gfx1201]
prereqs:
  common: [git, uv, rocminfo, hipcc]
install:
  rocm:
    - "test -d {src}/.git || git clone {repo}.git {src}"
    - "git -C {src} fetch origin {ref} && git -C {src} checkout -q {pinned}"
    - "python3 -m pip install --no-cache-dir -U 'packaging>=24.2' 'setuptools>=77'"
    - "cd {src} && ROCM_HOME=/opt/rocm CUDA_HOME=/opt/rocm python3 -m pip install --no-cache-dir -r requirements_rocm.txt"
    - "python3 -m pip install --no-cache-dir -r {src}/requirements_rocm.txt"
    - "cd {src} && GPU_ARCHS='{gpu_targets}' PYTORCH_ROCM_ARCH='{gpu_targets}' EXL3_BACKEND=rocm MAX_JOBS={jobs} python3 -m pip install --no-cache-dir --no-build-isolation ."
binary: "{src}/rocm_tools/exl3_server/server.py"
detect: "python3 -c 'import exllamav3; print(exllamav3.__version__)'"
launch: "python3 {binary} -m {model} -host {host} -port {port} -smn {alias} -cs 32768"
health: "GET /health"
alias_mode: flag
container:
  rocm:
    # setup.py refuses ROCm < 7.2.4 (the shared rocm/dev 7.0 base fails, CI #98); same base as sglang
    base: "rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e"
    # setup.py splits PYTORCH_ROCM_ARCH on spaces/commas (not ';') and supports
    # RDNA3/3.5/4 only: the shared fat list (gfx1030;...;gfx942) reached hipcc as
    # one bogus arch -> "undefined symbol: main" for every source (CI #98)
    gpu_targets: "gfx1100,gfx1101,gfx1102,gfx1150,gfx1151,gfx1200,gfx1201"
    apt: [hipcc]
upstream_watch: [README.md, requirements_rocm.txt, requirements_rocm10.txt, setup.py, rocm_tools/build_rocm10.sh, rocm_tools/exl3_server/server.py]
---

# ExLlamaV3 — ROCm fork (rocm_exl3)

A port of turboderp's ExLlamaV3 (tracks upstream v1.5.3) that needs no CUDA, for AMD RDNA.
It ships its **own OpenAI server** (`rocm_tools/exl3_server/server.py`). No releases, so
the skill pins a commit.

## Hardware parameters

- ROCm **>= 7.2.4** (the build hard-fails below that; ROCm 10 is recommended). The system path
  builds against the installed ROCm: `pip install -r requirements_rocm.txt` then
  `pip install --no-build-isolation .`. The ROCm 10 all-in-one path is
  `rocm_tools/build_rocm10.sh`.
- GPU: RDNA3/3.5 `gfx1100/1101/1102/1150/1151` (validated on gfx1151), RDNA4
  `gfx1200/1201` (builds, MoE slow, unvalidated). `GPU_ARCHS` / `PYTORCH_ROCM_ARCH` are set from
  `rocminfo`.
- No tensor-parallel. Vision is untested. Convert models on CUDA (`convert.py` is
  unexercised on RDNA).

## Launch

`server.py -m <exl3 dir> -host 127.0.0.1 -port 11434 -smn llm-local -cs 32768`
(default port 3953). Spec decoding: `-mtp -ndt 2`, `-dm <drafter>`, `-ngram N`.
MoE CPU offload: `-mcl N`. Routes: `/health`, `/v1/models`, `/v1/chat/completions`,
`/v1/completions`.
