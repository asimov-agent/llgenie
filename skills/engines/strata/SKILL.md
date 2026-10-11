---
name: engine-strata
description: "Use when installing Strata (Qwen3.8-Flash-Next 125B MoE across GPU/RAM/SSD; NVIDIA r580+ or AMD RDNA) and serving it as llm-local."
engine: "Strata"
id: strata
repo: https://github.com/Niko1221/Strata
ref: v0.1.42
ref_kind: tag
version: v0.1.42
pinned: 61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406
verified: "2026-10-11"
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
  cuda: [nvidia-smi, nvcc]
  rocm: [rocminfo, hipcc]
hw_flags:
  cuda:
    cuda_arch: "CUDA_ARCHITECTURES={cuda_arch}"
  rocm:
    gpu_targets: "GPU_TARGETS={gpu_targets}"
install:
  common:
    # Strata's own Dockerfile (v0.1.39) compiles the engine at image build time and
    # leaves the model download to the first start, so the image never runs the
    # interactive setup.sh. setup.py's cmake_build does the compile exactly as the
    # upstream Dockerfile does. The python env is a prefix install inside the image, never on a host.
    - "test -d {src}/.git || git clone -b v{version} --depth 1 {repo}.git {src}"
    - "git -C {src} fetch --depth 1 origin tag v{version} && git -C {src} checkout -q v{version}"
    - "python3 -m venv {src}/py && {src}/py/bin/pip install --no-cache-dir -r {src}/requirements.txt"
  cuda:
    - "cd {src} && CUDA_ARCHITECTURES='{cuda_arch}' py/bin/python -c 'import os,shutil,setup; llama=setup.get_llama_cpp(); nvcc,_=setup.find_nvcc(); arch=os.environ[\"CUDA_ARCHITECTURES\"]; setup.cmake_build(setup.ROOT, setup.ROOT/\"build\",\"strata\",[\"-DSTRATA_ENABLE_CUDA=ON\",\"-DSTRATA_BUILD_TESTS=OFF\",\"-DSTRATA_PORTABLE=ON\",\"-DCMAKE_CUDA_ARCHITECTURES=\"+arch,\"-DCMAKE_CUDA_COMPILER=\"+nvcc,\"-DSTRATA_GGML_DIR=\"+str(llama)],None,\"build-strata.bat\"); eng=setup.ROOT/\"engine\"; eng.mkdir(exist_ok=True); shutil.copy2(setup.ROOT/\"build\"/setup.EXE, eng/setup.EXE); import json; (eng/\"BUILD.json\").write_text(json.dumps(dict(source=\"local\", version=setup.source_version(), archs=sorted(int(x) for x in arch.split(\";\")), vision=\"none\", cuda_dirs=[d for d in (\"/usr/local/cuda/bin\",\"/usr/local/cuda/lib64\") if os.path.isdir(d)], src=setup.source_hash(setup.ENGINE_SOURCES), vision_src=None), indent=1))'"
  rocm:
    - "cd {src} && GPU_TARGETS='{gpu_targets}' py/bin/python -c 'import os,shutil,setup; llama=setup.get_llama_cpp(); arch=os.environ[\"GPU_TARGETS\"]; setup.cmake_build(setup.ROOT, setup.ROOT/\"build\",\"strata\",[\"-DSTRATA_ENABLE_HIP=ON\",\"-DSTRATA_BUILD_TESTS=OFF\",\"-DSTRATA_PORTABLE=ON\",\"-DGPU_TARGETS=\"+arch,\"-DSTRATA_GGML_DIR=\"+str(llama)],None,\"build-strata.bat\"); eng=setup.ROOT/\"engine\"; eng.mkdir(exist_ok=True); shutil.copy2(setup.ROOT/\"build\"/setup.EXE, eng/setup.EXE); import json; (eng/\"BUILD.json\").write_text(json.dumps(dict(source=\"local\", backend=\"hip\", version=setup.source_version(), archs=sorted(arch.split(\";\") if \";\" in arch else arch.split()), vision=\"none\", src=setup.source_hash(setup.ENGINE_SOURCES), vision_src=None), indent=1))'"
binary: "{src}/engine/strata"
detect: "{binary} --help 2>&1 | grep -q '^strata ' && echo {version}"
pre_launch: "cd {src} && choice=$(py/bin/python -c 'import os,sys,setup; c=setup.gguf_choice(os.path.basename(sys.argv[1])); print(\"--family %s --model %s\" % c if c else \"\")' {model}) && (test -n \"$choice\" || (echo \"[strata] $(basename {model}) is not a Strata model file (setup.py gguf_choice)\" >&2; exit 1)) && py/bin/python setup.py --setup --yes --no-start --no-browser --gguf-dir $(dirname {model}) $choice --data-dir /models/strata --port {port} --host {host}"
launch: "cd {src} && cfg=$(ls -t {src}/strata-*.json | head -1) && py/bin/python -c 'import json,sys; p,a=sys.argv[1:3]; c=json.load(open(p)); al=c.get(\"aliases\") or []; c[\"aliases\"]=al if a in al else al+[a]; json.dump(c,open(p,\"w\"),indent=1)' \"$cfg\" {alias} && py/bin/python serve/server.py --engine strata --config \"$cfg\" --port {port} --host {host}"
health: "GET /health"
alias_mode: config
container:
  cuda:
    apt: [libatomic1, libgomp1, python3-venv]
  rocm:
    base: "rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e"   # the shared rocm/dev 7.0 base has no HIP cmake package (CI #106)
    apt: [libatomic1, libgomp1, python3-venv]
upstream_watch: [setup.sh, setup.py, serve/server.py, docs/INSTALL.md, docs/DETAILS.md, Dockerfile, requirements.txt]
---

# Strata

A llama.cpp-derived C++ engine plus a Python server. It serves **only Qwen3.8-Flash-Next
(125B MoE)** and streams experts across GPU, RAM and SSD. Its image is built the way
Strata's own Dockerfile builds it: the engine is compiled into the image, and the model
is downloaded on the first start.

## Hardware parameters

- **cuda:** NVIDIA RTX 20-50 with >= 12 GB, driver r580+ / CUDA 13. The image compiles
  the engine for the fat CUDA arch list (`CUDA_ARCHITECTURES={cuda_arch}`), exactly as
  the upstream Dockerfile does, so one image covers RTX 20/30/40/50.
- **rocm:** RX 6800/6900 (gfx1030), 7900 XT/XTX (gfx1100), 7800/7700 (gfx1101),
  9060 XT (gfx1200), 9070 (gfx1201), R9700. The engine is compiled for the card.
- **RAM/SSD tiers (derived from free RAM):** `--resident-budget-gib N`,
  `--mmap-experts` / `--low-ram on`, `--vram-reserve-mib`, `--kv-resident`, `--kv q4_0|int8|k8v4`.
- Disk: about 80 GB (model) + 6 GB (MTP layer). Use an NVMe SSD.

## Serving as llm-local

`serve/server.py --config <strata-*.json> --host 127.0.0.1 --port 11434`. server.py has no alias
flag: the launch adds `llm-local` to the config's `aliases` (Strata #297), so `/v1/models` lists it
and replies carry it. The server answers any model name either way.
Routes: `/v1/chat/completions`, `/v1/messages`, `/v1/responses`, `/v1/models`, `/health`.

## Model files (llgenie)

Strata runs only the GGUF files its `setup.py` names (`MODELS` / `FAMILIES` / `HF_REVISIONS`).
`data/strata_models.json` is that table at the pinned commit (`make sync-strata-models`;
`make check-strata-models` fails on drift). llgenie downloads every shard of the choice
`setup.py --yes` makes on the host (`qwen` `IQ3_XXS` from 60 GB of RAM, else `qwen` `Q2_0`) from
its repo at its pinned revision, and `pre_launch` passes `--family` / `--model` from Strata's own
`gguf_choice(<first shard>)`, so setup never picks another size inside the container.
