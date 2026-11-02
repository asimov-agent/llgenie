---
name: engine-tensorrt-llm
description: "Use when installing NVIDIA TensorRT-LLM (Linux, Ampere+ CUDA 13 wheel pinned to torch 2.10 cu130) and serving trtllm-serve as llm-local."
engine: "TensorRT-LLM"
id: tensorrt-llm
repo: https://github.com/NVIDIA/TensorRT-LLM
ref: v1.2.1
ref_kind: tag
version: v1.2.1
pinned: 376f7e1bd8ed543f75014309e3fd4b237e9b0e73
verified: "2026-10-05"
license: Apache-2.0
servable: true
backends: [cuda]
os: [linux]
formats: [safetensors, trtllm-engine, fp8, nvfp4, awq, gptq]
requires:
  min_compute_cap:
    cuda: "8.0"
  min_cuda:
    cuda: "13.0"
prereqs:
  common: [uv, nvidia-smi, nvcc]
install:
  cuda:
    # Dated decision (issue #939, decided 2026-11-02): this stays a prebuilt wheel, not a source build.
    # A time-boxed source build at the pinned sha 376f7e1b was measured in the NGC devel:1.2.1 base
    # (`scripts/build_wheel.py --trt_root /opt/tensorrt --cuda_architectures 89-real -j 16` on a
    # 32-core host): a full LFS clone is 5.2 GB (8.6 GB with the venv+build tree), and object compile
    # projected to >90 min at -j16 on THIS 32-core host before wheel/link — on the 4-vCPU
    # GitHub-hosted `ubuntu-latest` the engine-build job runs on, that is ~4-8x slower => multi-hour,
    # far past the 240-min CI timeout, and the clone+venv+build tree (~11+ GB) already approaches the
    # runner's ~14 GB free disk. Recorded in docs/ENGINES.md as a recorded exception; delete the
    # decision comment when upstream ships a wheel-free build that fits a CI budget.
    - "uv pip install --system --break-system-packages torch==2.10.0 torchvision --index-url https://download.pytorch.org/whl/cu130"
    - "python3 -c 'import torch; print(\"torch==\" + torch.__version__)' > {prefix}/torch-constraint.txt"
    - "uv pip install --system --break-system-packages tensorrt_llm=={version} -c {prefix}/torch-constraint.txt"
env:
  cuda:
    CUDA_HOME: "$(dirname $(dirname $(command -v nvcc)))"
binary: "trtllm-serve"
binary_flags: ["--help"]   # trtllm-serve is argparse (NVIDIA's CLI reference lists its options)
binary_probe:
  cuda: device   # importing tensorrt_llm needs the CUDA device, so --help cannot answer on a GPU-less runner
detect: "python3 -c 'import importlib.metadata as m; print(m.version(\"tensorrt_llm\"))'"
launch: "{binary} {model} --host {host} --port {port} --backend pytorch --kv_cache_free_gpu_memory_fraction 0.9"
pre_launch: "mkdir -p {prefix}/served && ln -sfn {model} {prefix}/served/{alias}"
health: "GET /health"
alias_mode: symlink
container:
  cuda:     # official NGC image
    base: "nvcr.io/nvidia/tensorrt-llm/release:{version}"
    prebuilt: true
upstream_watch: [tensorrt_llm/version.py, tensorrt_llm/commands/serve.py, tensorrt_llm/serve/openai_server.py, requirements.txt, docs/source/installation/linux.md]
---

# TensorRT-LLM

NVIDIA CUDA only, Linux only, compute capability **>= 8.0** (Ampere, Ada 8.9, Hopper,
Blackwell). The wheel is built against **CUDA 13.0 + PyTorch 2.10**. Torch is
installed first from the cu130 index and pinned with a constraint file.
Otherwise pip downgrades torch. OpenMPI is a system dependency (`libopenmpi-dev` /
`openmpi`). Install it with the OS package manager when import fails.

## Serving as llm-local

`trtllm-serve` 1.2.1 has no `--served-model-name`. For a local directory it advertises
the **directory name** (`openai_server.py`: `self.model = model_dir.name`). So the skill
symlinks the model dir as `<prefix>/served/llm-local` and the launcher passes
that path as `{model}`. Routes: `/v1/models`, `/v1/chat/completions`,
`/v1/completions`, `/health`, `/metrics`. No GGUF.
