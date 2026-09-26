# CI variant-build image (issue #84/#89): one image for all ubuntu-latest
# CPU + CUDA jobs. Has the FULL CUDA toolkit (nvcc) for the cuda variants AND
# Python + the repo's pip deps (gguf, numpy, huggingface_hub[cli]) so the same
# image can (a) clone-or-pull + build each tree x backend and (b) run the
# 0.5B "hi" health check. Builds on the host and in CI from the SAME Dockerfile
# (single code path, no fallback).
#
#   make test-variant-image
FROM nvidia/cuda:12.4.0-devel-ubuntu22.04

# nvcc under /usr/local/cuda/bin; put it on PATH so build_llama_server.sh's
# nvcc preflight resolves it (PATH first, then /opt/cuda, /usr/local/cuda).
ENV PATH=/usr/local/cuda/bin:${PATH} \
    CUDA_HOME=/usr/local/cuda \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH}

# Build toolchain (git, cmake, g++, gfortran, ldd via binutils, curl) + python.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential cmake gfortran curl python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Make the CUDA *driver* stub (libcuda.so.1) linker-visible, exactly like a real
# NVIDIA box. On a real machine the GPU *driver* installs libcuda.so.1 into
# /usr/lib/x86_64-linux-gnu/ — that is what resolves the cu* driver symbols at
# *link* time. The CUDA *toolkit* image ships no driver; its only copy of the
# driver stub lives under <cuda>/compat/, which is NOT on the linker's default
# search path. Shared libs (libggml-cuda.so) tolerate unresolved driver symbols
# because they are linked lazily, but the final llama-server EXECUTABLE must
# resolve them at link time — so without this step `llama-server` fails to link
# in CI. Symlinking the compat stubs into the standard lib dir + ldconfig mirrors
# a real driver install and makes the CI CUDA build byte-identical to host.
RUN ln -sf /usr/local/cuda-12.4/compat/libcuda.so.1 /usr/lib/x86_64-linux-gnu/libcuda.so.1 \
    && ln -sf /usr/local/cuda-12.4/compat/libcuda.so.1 /usr/lib/libcuda.so.1 \
    && ldconfig \
    && ldconfig -p | grep -E "libcuda\.so\.1"

# Copy the compiled lockfiles (requirements.txt + requirements-dev.txt are
# the single sources of truth, generated via make generate-requirements) and
# the repo, then install the runtime + dev deps + the hf CLI. This lets the
# SAME image do the builds AND the 0.5B "hi" health check (which shells out to
# $HF_BIN). Never hand-edit requirements.txt — it is regenerated from .in.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir \
        -r requirements.txt \
        -r requirements-dev.txt \
        "huggingface_hub[cli]>=0.30"
WORKDIR /repo
CMD ["--help"]
