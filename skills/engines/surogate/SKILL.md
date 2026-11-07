---
name: engine-surogate
description: "Use when installing the Surogate serving engine (invergent-ai/surogate, published cu130 wheel) into the cuda engine image and serving GGUF / safetensors models as llm-local."
engine: "Surogate"
id: surogate
repo: "https://github.com/invergent-ai/surogate"
ref: v1.5.15
ref_kind: tag
version: v1.5.15
pinned: ad6c0bbf1f5c43e4ad844fcc02af5406a9323b0b
verified: "2026-11-07"
license: Apache-2.0
servable: true
backends: [cuda]
os: [linux]
formats: [gguf, safetensors]
prereqs:
  common: [uv]
install:
  # A published manylinux wheel install (upstream's own Dockerfile.cu130 does the same
  # closure: torch cu130 + torchvision/audio from the pytorch index, then the wheel +
  # the nvidia-* runtime python wheels + the glib/X11 client libs the audited engine
  # binaries need to load). The engine is the precompiled product; the cu130 ABI is the
  # floor upstream states for the W8/NVFP4 serving kernels. There is no CUDA 12 package.
  cuda:
    # system python for the shared cuda devel base is 3.12 (nvidia/cuda:13.0.2-devel-ubuntu24.04)
    # — the wheel's cp312-abi3 tag matches. The upstream Dockerfile.cu130 creates a venv;
    # llgenie installs into the image's own python instead (the container is the isolation).
    - "uv pip install --system --break-system-packages 'torch==2.11.0+cu130' 'torchvision==0.26.0+cu130' 'torchaudio==2.11.0+cu130' --index-url https://download.pytorch.org/whl/cu130"
    - "uv pip install --system --break-system-packages https://github.com/invergent-ai/surogate/releases/download/v{version}/surogate-{version}+cu130-cp312-abi3-manylinux_2_39_x86_64.whl"
    # the wheel pins its own nvidia runtime wheels; these are the same versions upstream's
    # Dockerfile.cu130 installs after the wheel so the loader finds libcudart/cudnn/nccl
    - "uv pip install --system --break-system-packages 'nvidia-cuda-runtime==13.1.80' 'nvidia-cudnn-cu13>=9.10.2.21' 'nvidia-nccl-cu13==2.29.3' 'nvidia-cufile==1.16.1.26' 'nvidia-cuda-nvrtc==13.1.115'"
    # the engine loads more than the trainer: audited wheels vendor FFmpeg/numa/ICU but leave
    # glib/gobject and the X11 client libraries to the system (40 unresolved refs to libglib
    # on a bare image without them — upstream's own comment, Dockerfile.cu130).
    - "apt-get update && apt-get install -y --no-install-recommends libglib2.0-0t64 libx11-6 libxext6 libxrender1 && rm -rf /var/lib/apt/lists/*"
    # expose the cu13 lib path the engine's RPATH points at (site-packages/nvidia/.../cu13/lib)
    - "python3 -c 'import site; p=site.getsitepackages()[0]; f=open(\"/etc/ld.so.conf.d/surogate-cu13.conf\",\"w\"); f.write(p+\"/nvidia/cuda_runtime/lib\\n\"+p+\"/nvidia/cudnn/lib\\n\"+p+\"/nvidia/nccl/lib\\n\"+p+\"/nvidia/cufile/lib\\n\"); f.close()' && ldconfig"
binary: "surogate"
binary_flags: ["--version"]   # a documented flag; see binary_probe (device policy skips the flag probe on a GPU-less runner)
binary_probe:
  cuda: device   # surogate --help imports _surogate (the CUDA engine binary), which needs libcuda.so.1 present only at runtime — so the build/CI flag probe is skipped and the version is proven by the image's own detect
detect:
  cuda: "python3 -c 'import importlib.metadata as m; v=m.version(\"surogate\"); print(\"surogate\", v if v else \"{version}\")'"
launch:
  cuda: "{binary} serve {model} --host {host} --port {port} --served-model-name {alias}"
health: "GET /health"
alias_mode: flag
container:
  cuda:
    apt: [libglib2.0-0t64, libx11-6, libxext6, libxrender1]
upstream_watch: [Dockerfile.cu130, pyproject.toml, surogate/cli/serve.py, RELEASE_v1.4.0.md]
---

# Surogate

Upstream: https://github.com/invergent-ai/surogate

Registry note: Auto-registered from
https://lightbrd.com/OwnYourCompute/status/2116885470403801334 — Train and serve
LLMs at extreme speed and massive throughput.

Servable via the published `manylinux_2_39_x86_64` cu130 wheel
(`surogate-<version>+cu130-cp312-abi3-...`); the engine is the precompiled binary, so
llgenie installs the wheel into the shared cuda base image's own Python 3.12 and serves
with `surogate serve`. There is no CUDA 12 package: upstream states the serving engine's
W8/NVFP4 kernels need more shared memory per block than a CUDA 12 toolkit will assemble for
the RTX line, so CUDA 13.0 is the floor and the cuda backend must run on a cu130 image.

## Launch

`surogate serve <hf-id | local safetensors dir | .gguf> --host 127.0.0.1 --port 11434
--served-model-name llm-local`. The first launch prepares and caches the checkpoint; later
launches reuse that preparation. Routes per `docs/inference/api.md`: `/v1/chat/completions`,
`/v1/completions`, `/v1/models`, `/health` (auth-exempt, so the engine image health probe
needs no API key). Requires an NVIDIA GPU (a CUDA-capable device; the reader's card).

## Hardware parameters

- backends: `cuda` only — a native CUDA engine, no ROCm/Vulkan/Metal. No CPU variant.
- wheel abi: `cp312-abi3-manylinux_2_39_x86_64` — x86_64 only (the aarch64 wheel is for the
  DGX Spark GB10 build and is not a general ARM server).
