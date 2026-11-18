---
name: engine-edge0
description: "Use when installing Edge0's edge0-strata engine (Edge0 145B/120B latent MoE served from a multi-file pack directory; NVIDIA CUDA 13) and serving edge0-145b as llm-local."
engine: "edge0"
id: edge0
repo: https://github.com/Edge0-AI/Edge0
ref: main
ref_kind: branch
pinned: 4a7964de4b337532aad74b03714125deb7506e70
verified: "2026-11-18"
license: MIT
servable: true
backends: [cuda]
os: [linux]
formats: [pack]

# Pack contract (#2909): model dir mounted at /models/<pack>, parts verified, config_env bound per part.
model_contract: "pack"
pack:
  parts: [model-skeleton.gguf, ple-fp8.gguf, profile.bin, experts.bin, labels.bin, dense.bin, mtp, tokenizer]
  config_env:
    STRATA_LATENT_A: experts.bin
    STRATA_LATENT_LABELS: labels.bin
    STRATA_LATENT_DENSE: dense.bin
models: ["Edge0-145B"]
requires:
  min_compute_cap:
    cuda: "7.5"
prereqs:
  common: [git, python3, curl]
  cuda: [nvidia-smi, nvcc]
hw_flags:
  cuda:
    cuda_arch: "CUDA_ARCHITECTURES={cuda_arch}"
install:
  common:
    # edge0-strata is a Strata fork; the engine source lives at edge0-strata/ in the
    # Edge0-AI/Edge0 tree. The checkout pattern pins exactly `pinned` in image builds.
    - "test -d {src}/.git || git clone -b {ref} {repo}.git {src}"
    - "git -C {src} fetch origin {ref}"
    - "git -C {src} checkout -B {ref} {checkout}"
    # EDGE0.md v5 "Build (Linux, NVIDIA)": ggml comes from llama.cpp at the pinned snapshot.
    - "test -d {src}/edge0-strata/third_party/llama.cpp/.git || git clone https://github.com/ggml-org/llama.cpp {src}/edge0-strata/third_party/llama.cpp"
    - "git -C {src}/edge0-strata/third_party/llama.cpp checkout 3cf03257f219afbe7334045ff7c6a06ac68c627d"
    # EDGE0.md's own fallback when uv is unavailable: python -m venv + the pinned requirements.
    - "python3 -m venv {src}/edge0-strata/.venv && {src}/edge0-strata/.venv/bin/pip install --no-cache-dir -r {src}/edge0-strata/requirements.txt"
  cuda:
    - "cd {src}/edge0-strata && PATH=/usr/local/cuda/bin:$PATH cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_COMPILER=\"$(command -v nvcc)\" -DCMAKE_CUDA_ARCHITECTURES='{cuda_arch}' -DSTRATA_ENABLE_CUDA=ON -DSTRATA_GGML_DIR=\"$PWD/third_party/llama.cpp\" && cmake --build build --target strata"
binary: "{src}/edge0-strata/build/strata"
binary_flags: ["--version", "--help"]   # the strata-family CLI answers both (measured on the strata engine's own binary)
detect: "{binary} --version"
pre_launch: "cd {src}/edge0-strata && python3 -c 'import json,os,sys; p=os.path.abspath(sys.argv[1]); assert os.path.isdir(p), (\"[edge0] \" + p + \" is not a pack directory (model_contract=pack, launch contract v5)\"); t=json.load(open(\"edge0/models/edge0-145b.json\")); r=lambda v: v.replace(\"${{MODEL_DIR}}\", p).replace(\"${{STRATA_DIR}}\", os.getcwd()).replace(\"${{EXE_SUFFIX}}\", \"\").replace(\"${{CUDA_LIB_DIR}}\", \"\").replace(\"${{DU_FILE}}\", os.path.join(p, \"dense.bin\")).replace(\"${{DU_FMT}}\", \"Q8\").replace(\"${{LAT_FUSED_Q3K}}\", \"1\" if os.path.basename(p).lower().endswith(\"-q3k\") else \"0\").replace(\"${{PLE_IO}}\", \"direct\"); t[\"exe\"]=r(t[\"exe\"]); t[\"args\"]=[r(a) for a in t[\"args\"]]; t[\"tokenizer\"]=r(t[\"tokenizer\"]); t[\"env\"]=dict((k, r(v)) for k, v in t[\"env\"].items()); t[\"lib_dirs\"]=[r(x) for x in t[\"lib_dirs\"]]; t[\"model_name\"]=\"{alias}\"; json.dump(t, open(\"edge0-ready.json\", \"w\"), indent=1)' {model}"
launch: "cd {src}/edge0-strata && .venv/bin/python serve/server.py --engine strata --config {src}/edge0-strata/edge0-ready.json --api-key none --port {port} --host {host}"
health: "GET /health"
alias_mode: config
container:
  cuda:
    apt: [libatomic1, libgomp1, python3-venv, libnuma1, tini, zlib1g]   # the strata engine family's runtime libs (same fork)
upstream_watch: [edge0-strata/CMakeLists.txt, edge0-strata/serve/server.py, edge0-strata/requirements.txt, edge0-strata/EDGE0.md, edge0-strata/edge0/models/edge0-145b.json]
---
