---
name: engine-vllm
description: "Use when building the vLLM engine image from source (clone at the pin, compile CUDA/ROCm/CPU kernels) and serving as llm-local."
engine: "vLLM"
id: vllm
repo: https://github.com/vllm-project/vllm
ref: v0.33.0
ref_kind: tag
version: v0.33.0
pinned: 3a4d82f569a9f57054ba81633e9b6c73b34b51fe
verified: "2026-11-02"
license: Apache-2.0
servable: true
backends: [cuda, rocm, cpu]
os: [linux]
formats: [safetensors, awq, gptq, fp8, gguf]
requires:
  min_compute_cap:
    cuda: "7.5"
  gpu_targets:
    rocm: [gfx942, gfx1100, gfx1101, gfx1201]
prereqs:
  common: [uv]
  cuda: [nvidia-smi]
  rocm: [rocminfo]
hw_flags:
  cuda:
    cuda_arch: "'-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}'"
  rocm:
    gpu_targets: "'{gpu_targets}'"
install:
  cuda:
    - "test -d {src}/.git || git clone -b {ref} --depth 1 {repo}.git {src}"
    # --no-build-isolation builds against a preinstalled torch: bump >= the sha's own
    # torch pin from the matching PyTorch repack index, then the rest of vLLM's build deps.
    # torchcodec (the vLLM video-decoding backend, `>= 0.14` in requirements/*.txt) is
    # preinstalled from the SAME index: the default-PyPI wheel is built against the stable
    # torch C++ ABI and `torch.ops.load_library(libtorchcodec_image.so)` dies with a generic
    # "Could not load this library" against the preinstalled torch (issue #1365 run
    # 41355299891 cpu/cuda).
    - "uv pip install --system --break-system-packages torch==2.14.0 torchvision torchaudio torchcodec --index-url https://download.pytorch.org/whl/{torch_backend}"
    - "uv pip install --system --break-system-packages -r {src}/requirements/build/cuda.txt --index-strategy unsafe-best-match"
    # vllm 5df63a72 ships a vendored Rust frontend (vllm-rs, channel 1.95): setup.py falls back to a
    # local `cargo` build when the precompiled vllm/vllm-rs + _rust_*.so artifacts are absent, so the
    # shared devel base (no Rust toolchain) fails. build_rust.sh bootstraps rustup + the pinned
    # toolchain and precompiles the artifacts into the source tree, letting -e . skip cargo (issue #1365).
    - "cd {src} && bash tools/build_rust.sh"
    # ubuntu-latest has 16 GiB. Uncapped ninja starts one nvcc per core, each fat-compiling
    # 75;80;86;89;90;120, and the kernel SIGKILLs the build (run 41696864556: `make: Killed`,
    # then the runner shutdown signal, ~60 min in, no compiler error). Keep an EXPLICIT job cap
    # (never uncapped), sized per vLLM's own build docs Troubleshooting, which sets MAX_JOBS=6
    # as the "avoid being overloaded" example and calls lower values "a much slower build
    # process" (docs/getting_started/installation/gpu.md). MAX_JOBS=6 keeps the guard's intent
    # (6 fat nvcc ≈ ~10-12 GiB peak, within the 16 GiB runner) while roughly 2-3x the compile of
    # the old MAX_JOBS=2. Do not raise the 240-minute cell timeout for this (owner closed #1609).
    - "cd {src} && MAX_JOBS=6 CMAKE_BUILD_PARALLEL_LEVEL=6 CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}' VLLM_TARGET_DEVICE=cuda uv pip install --system --break-system-packages --no-build-isolation -e ."
  rocm:
    - "test -d {src}/.git || git clone -b {ref} --depth 1 {repo}.git {src}"
    # the rocm build file names the amd index and the torch it needs, but pins a BARE
    # triton (3.7.1+git0263a6a6) while torch==2.12.0+rocm7.14.0 requires the rocm-suffixed
    # wheel (triton==3.7.1+git0263a6a6.rocm7.14.0) — upstream pin defect at 5df63a72; the
    # resolver reports 'your requirements are unsatisfiable' unless the pins agree.
    - "cd {src} && sed -i 's/^triton==3.7.1+git0263a6a6$/triton==3.7.1+git0263a6a6.rocm7.14.0/' requirements/build/rocm.txt && uv pip install --system --break-system-packages -r requirements/build/rocm.txt --index-strategy unsafe-best-match"
    # vendored Rust frontend (vllm-rs): build_rust.sh precompiles the artifacts so -e . skips cargo
    - "cd {src} && bash tools/build_rust.sh"
    # the -e . CMake step must resolve HIP against the BASE image's /opt/rocm (which ships
    # hipcc + FindHIP.cmake): without ROCM_PATH/HIP_PATH/CMAKE_MODULE_PATH pointing there, torch's
    # LoadHIP.cmake falls back to the pip rocm-sdk-core wheel path and fails 'No FindHIP.cmake in
    # CMAKE_MODULE_PATH' / 'Optional package HIP not found' (issue #1365, run 41342311363 rocm).
    # --no-build-isolation must ALSO resolve TheRock device extras against the AMD index. Step 2
    # (`-r requirements/build/rocm.txt`) gets `--extra-index-url https://repo.amd.com/rocm/whl-multi-arch/`
    # from that requirements file, so rocm==7.14.0 is importable and setup.py::get_rocm_device_requirements()
    # emits rocm/torch/torchvision[device-gfx<arch>] extras. The `-e .` command does not read rocm.txt, so
    # without the flag on this line uv resolves those extras from PyPI's placeholder rocm==0.1.0
    # (poetry-built sdist, no wheel) and dies with 'No module named poetry' (issue #1558).
    # `ninja -j $(nproc)` is already what vLLM's setup.py requests. ROCm clang 20 (roc-7.0.0) has no
    # --offload-jobs, so one clang++ still walks every --offload-arch one cc1 at a time. The launcher
    # below runs `clang++ -###` and executes those per-arch device jobs concurrently (one slot budget
    # shared with ninja). Same fat gfx list, same bundled object. Do not "fix" the wall time by raising
    # engine-build.yml's 240-minute cell timeout (owner closed that in #1609).
    # HIP_PARALLEL_JOBS is the launcher's cross-process slot budget (shared with ninja); when unset it
    # defaults to `os.cpu_count()` (16 on ubuntu-latest) — that many concurrent cc1 HIP device jobs on
    # top of ninja's host TUs reproducibly SIGKILLs the 16 GiB runner mid-compile (`make: Killed`), the
    # same failure the cuda leg already caps with MAX_JOBS=6. Cap explicitly at 6 (vLLM's docs'
    # "avoid overload" example) so the frozen image builds on the runner it is actually built on.
    - "echo IyEvdXNyL2Jpbi9lbnYgcHl0aG9uMwoiIiJDb21waWxlIGEgbXVsdGktYXJjaCBISVAgdHJhbnNsYXRpb24gdW5pdCB3aXRoIG9uZSBwcm9jZXNzIHBlciBHUFUgdGFyZ2V0LgoKUk9DbSBjbGFuZyAyMCAocm9jLTcuMC4wKSBhY2NlcHRzIHNldmVyYWwgYGAtLW9mZmxvYWQtYXJjaD1gYCBmbGFncyBhbmQgdGhlbgpydW5zIHRoZSBkZXZpY2UgY29tcGlsZSBmb3IgZWFjaCBhcmNoaXRlY3R1cmUgb25lIGFmdGVyIGFub3RoZXIuIEl0IGhhcyBubwpgYC0tb2ZmbG9hZC1qb2JzYGAgZmxhZy4gYGBjbGFuZysrIC0jIyNgYCBwcmludHMgdGhhdCBwbGFuLiBEZXZpY2Ugam9icyBmb3IKZGlmZmVyZW50IGFyY2hpdGVjdHVyZXMgd3JpdGUgZGlmZmVyZW50IG91dHB1dHMsIHNvIHRoaXMgbGF1bmNoZXIgcnVucyB0aG9zZQpncm91cHMgYXQgb25jZSwgdGhlbiB0aGUgb2ZmbG9hZCBidW5kbGVyIGFuZCB0aGUgaG9zdCBjb21waWxlIGluIG9yZGVyLgoKQ01ha2UgaW52b2tlcyBpdCBhcyBgYGhpcF9vZmZsb2FkX3BhcmFsbGVsLnB5IDxjb21waWxlcj4gPGFyZ3MuLi4+YGAKKGBgQ01BS0VfSElQX0NPTVBJTEVSX0xBVU5DSEVSYGAgLyBgYENNQUtFX0NYWF9DT01QSUxFUl9MQVVOQ0hFUmBgKS4KQSBjb21tYW5kIHdpdGggZmV3ZXIgdGhhbiB0d28gb2ZmbG9hZCBhcmNoaXRlY3R1cmVzIGlzIGV4ZWN1dGVkIHVuY2hhbmdlZC4KU2V0IGBgSElQX1BBUkFMTEVMPTBgYCB0byBmb3JjZSB0aGF0IHBhdGguIGBgSElQX1BBUkFMTEVMX0pPQlNgYCBjYXBzIGhvdyBtYW55CmRldmljZSBqb2JzIHJ1biBhdCBvbmNlIGFjcm9zcyBldmVyeSBsYXVuY2hlciBpbiB0aGUgYnVpbGQgKGRlZmF1bHQ6IG5wcm9jKS4KIiIiCmZyb20gX19mdXR1cmVfXyBpbXBvcnQgYW5ub3RhdGlvbnMKCmltcG9ydCBmY250bAppbXBvcnQgb3MKaW1wb3J0IHNobGV4CmltcG9ydCBzdWJwcm9jZXNzCmltcG9ydCBzeXMKaW1wb3J0IHRpbWUKZnJvbSBjb25jdXJyZW50LmZ1dHVyZXMgaW1wb3J0IFRocmVhZFBvb2xFeGVjdXRvciwgYXNfY29tcGxldGVkCgoKZGVmIF9hcmNoKGFyZ3Y6IGxpc3Rbc3RyXSkgLT4gc3RyIHwgTm9uZToKICAgIGZvciBpLCBhcmcgaW4gZW51bWVyYXRlKGFyZ3YpOgogICAgICAgIGlmIGFyZyA9PSAiLXRhcmdldC1jcHUiIGFuZCBpICsgMSA8IGxlbihhcmd2KSBhbmQgYXJndltpICsgMV0uc3RhcnRzd2l0aCgiZ2Z4Iik6CiAgICAgICAgICAgIHJldHVybiBhcmd2W2kgKyAxXQogICAgICAgIG1hcmsgPSAibWNwdT1nZngiCiAgICAgICAgYXQgPSBhcmcuZmluZChtYXJrKQogICAgICAgIGlmIGF0ID49IDA6CiAgICAgICAgICAgIHJldHVybiBhcmdbYXQgKyBsZW4oIm1jcHU9IikgOl0uc3BsaXQoIiwiKVswXQogICAgcmV0dXJuIE5vbmUKCgpkZWYgX2pvYnModGV4dDogc3RyKSAtPiBsaXN0W2xpc3Rbc3RyXV06CiAgICBmb3VuZCA9IFtdCiAgICBmb3IgbGluZSBpbiB0ZXh0LnNwbGl0bGluZXMoKToKICAgICAgICBzdHJpcHBlZCA9IGxpbmUuc3RyaXAoKQogICAgICAgIGlmIHN0cmlwcGVkLnN0YXJ0c3dpdGgoJyInKToKICAgICAgICAgICAgZm91bmQuYXBwZW5kKHNobGV4LnNwbGl0KHN0cmlwcGVkKSkKICAgIHJldHVybiBmb3VuZAoKCmNsYXNzIF9TbG90czoKICAgICIiIkNyb3NzLXByb2Nlc3MgY2FwIHNvIG5pbmphIC1qIGFuZCBwZXItYXJjaCBmYW4tb3V0IHNoYXJlIG9uZSBidWRnZXQuIiIiCgogICAgZGVmIF9faW5pdF9fKHNlbGYsIG46IGludCkgLT4gTm9uZToKICAgICAgICBzZWxmLm4gPSBtYXgoMSwgbikKICAgICAgICBzZWxmLmRpciA9ICIvdG1wL2hpcC1wYXJhbGxlbC1zbG90cyIKICAgICAgICBvcy5tYWtlZGlycyhzZWxmLmRpciwgZXhpc3Rfb2s9VHJ1ZSkKCiAgICBkZWYgcnVuKHNlbGYsIGFyZ3Y6IGxpc3Rbc3RyXSkgLT4gaW50OgogICAgICAgIHdoaWxlIFRydWU6CiAgICAgICAgICAgIGZvciBpIGluIHJhbmdlKHNlbGYubik6CiAgICAgICAgICAgICAgICBoYW5kbGUgPSBvcGVuKG9zLnBhdGguam9pbihzZWxmLmRpciwgc3RyKGkpKSwgImErIikKICAgICAgICAgICAgICAgIHRyeToKICAgICAgICAgICAgICAgICAgICBmY250bC5mbG9jayhoYW5kbGUuZmlsZW5vKCksIGZjbnRsLkxPQ0tfRVggfCBmY250bC5MT0NLX05CKQogICAgICAgICAgICAgICAgZXhjZXB0IEJsb2NraW5nSU9FcnJvcjoKICAgICAgICAgICAgICAgICAgICBoYW5kbGUuY2xvc2UoKQogICAgICAgICAgICAgICAgICAgIGNvbnRpbnVlCiAgICAgICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHN1YnByb2Nlc3MucnVuKGFyZ3YpLnJldHVybmNvZGUKICAgICAgICAgICAgICAgIGZpbmFsbHk6CiAgICAgICAgICAgICAgICAgICAgaGFuZGxlLmNsb3NlKCkKICAgICAgICAgICAgdGltZS5zbGVlcCgwLjA1KQoKCmRlZiBfcnVuX3NlcShzbG90czogX1Nsb3RzLCBqb2JzOiBsaXN0W2xpc3Rbc3RyXV0pIC0+IGludDoKICAgIGZvciBqb2IgaW4gam9iczoKICAgICAgICByYyA9IHNsb3RzLnJ1bihqb2IpCiAgICAgICAgaWYgcmM6CiAgICAgICAgICAgIHJldHVybiByYwogICAgcmV0dXJuIDAKCgpkZWYgbWFpbigpIC0+IE5vbmU6CiAgICBpZiBsZW4oc3lzLmFyZ3YpIDwgMjoKICAgICAgICBzeXMuZXhpdCgidXNhZ2U6IGhpcF9vZmZsb2FkX3BhcmFsbGVsLnB5IDxjb21waWxlcj4gW2FyZ3MuLi5dIikKICAgIGNvbXBpbGVyLCBhcmdzID0gc3lzLmFyZ3ZbMV0sIHN5cy5hcmd2WzI6XQogICAgYXJjaHMgPSBbYS5zcGxpdCgiPSIsIDEpWzFdIGZvciBhIGluIGFyZ3MgaWYgYS5zdGFydHN3aXRoKCItLW9mZmxvYWQtYXJjaD0iKV0KICAgIHBsYWluID0gb3MuZW52aXJvbi5nZXQoIkhJUF9QQVJBTExFTCIpID09ICIwIiBvciAiLWMiIG5vdCBpbiBhcmdzIG9yIGxlbihhcmNocykgPCAyCiAgICBpZiBwbGFpbjoKICAgICAgICBvcy5leGVjdnAoY29tcGlsZXIsIFtjb21waWxlciwgKmFyZ3NdKQogICAgcHJvYmUgPSBzdWJwcm9jZXNzLnJ1bihbY29tcGlsZXIsICItIyMjIiwgKmFyZ3NdLCBjYXB0dXJlX291dHB1dD1UcnVlLCB0ZXh0PVRydWUpCiAgICBqb2JzID0gX2pvYnMocHJvYmUuc3RkZXJyKQogICAgYnVuZGxlcl9hdCA9IG5leHQoKGkgZm9yIGksIGpvYiBpbiBlbnVtZXJhdGUoam9icykgaWYgYW55KCJjbGFuZy1vZmZsb2FkLWJ1bmRsZXIiIGluIGEgZm9yIGEgaW4gam9iKSksIE5vbmUpCiAgICBpZiBub3Qgam9icyBvciBidW5kbGVyX2F0IGlzIE5vbmU6CiAgICAgICAgb3MuZXhlY3ZwKGNvbXBpbGVyLCBbY29tcGlsZXIsICphcmdzXSkKICAgIGdyb3VwczogZGljdFtzdHIsIGxpc3RbbGlzdFtzdHJdXV0gPSB7fQogICAgb3JkZXI6IGxpc3Rbc3RyXSA9IFtdCiAgICBmb3Igam9iIGluIGpvYnNbOmJ1bmRsZXJfYXRdOgogICAgICAgIGtleSA9IF9hcmNoKGpvYikKICAgICAgICBpZiBrZXkgaXMgTm9uZToKICAgICAgICAgICAgcmMgPSBzdWJwcm9jZXNzLnJ1bihqb2IpLnJldHVybmNvZGUKICAgICAgICAgICAgaWYgcmM6CiAgICAgICAgICAgICAgICBzeXMuZXhpdChyYykKICAgICAgICAgICAgY29udGludWUKICAgICAgICBpZiBrZXkgbm90IGluIGdyb3VwczoKICAgICAgICAgICAgZ3JvdXBzW2tleV0gPSBbXQogICAgICAgICAgICBvcmRlci5hcHBlbmQoa2V5KQogICAgICAgIGdyb3Vwc1trZXldLmFwcGVuZChqb2IpCiAgICBzbG90cyA9IF9TbG90cyhpbnQob3MuZW52aXJvbi5nZXQoIkhJUF9QQVJBTExFTF9KT0JTIikgb3Igb3MuY3B1X2NvdW50KCkgb3IgOCkpCiAgICB3b3JrZXJzID0gbWluKGxlbihvcmRlciksIHNsb3RzLm4pIG9yIDEKICAgIHdpdGggVGhyZWFkUG9vbEV4ZWN1dG9yKG1heF93b3JrZXJzPXdvcmtlcnMpIGFzIHBvb2w6CiAgICAgICAgZnV0dXJlcyA9IFtwb29sLnN1Ym1pdChfcnVuX3NlcSwgc2xvdHMsIGdyb3Vwc1trZXldKSBmb3Iga2V5IGluIG9yZGVyXQogICAgICAgIGZvciBmdXR1cmUgaW4gYXNfY29tcGxldGVkKGZ1dHVyZXMpOgogICAgICAgICAgICByYyA9IGZ1dHVyZS5yZXN1bHQoKQogICAgICAgICAgICBpZiByYzoKICAgICAgICAgICAgICAgIHN5cy5leGl0KHJjKQogICAgZm9yIGpvYiBpbiBqb2JzW2J1bmRsZXJfYXQ6XToKICAgICAgICByYyA9IHN1YnByb2Nlc3MucnVuKGpvYikucmV0dXJuY29kZQogICAgICAgIGlmIHJjOgogICAgICAgICAgICBzeXMuZXhpdChyYykKCgppZiBfX25hbWVfXyA9PSAiX19tYWluX18iOgogICAgbWFpbigpCg== | base64 -d > /opt/llgenie/bin/hip_offload_parallel.py && chmod +x /opt/llgenie/bin/hip_offload_parallel.py"
    - "cd {src} && HIP_PARALLEL_JOBS=6 ROCM_HOME=/opt/rocm ROCM_PATH=/opt/rocm HIP_PATH=/opt/rocm CMAKE_HIP_COMPILER_LAUNCHER=/opt/llgenie/bin/hip_offload_parallel.py CMAKE_CXX_COMPILER_LAUNCHER=/opt/llgenie/bin/hip_offload_parallel.py CMAKE_ARGS='-DROCM_PATH=/opt/rocm -DCMAKE_PREFIX_PATH=/opt/rocm -DCMAKE_MODULE_PATH=/opt/rocm/lib/cmake/hip;/opt/rocm/lib/cmake/hip-lang -DCMAKE_HIP_COMPILER_LAUNCHER=/opt/llgenie/bin/hip_offload_parallel.py -DCMAKE_CXX_COMPILER_LAUNCHER=/opt/llgenie/bin/hip_offload_parallel.py' PYTORCH_ROCM_ARCH='{gpu_targets}' VLLM_TARGET_DEVICE=rocm uv pip install --system --break-system-packages --no-build-isolation --extra-index-url https://repo.amd.com/rocm/whl-multi-arch/ --index-strategy unsafe-best-match -e ."

  cpu:
    - "test -d {src}/.git || git clone -b {ref} --depth 1 {repo}.git {src}"
    # the pinned cpu.txt requests torch==2.14.0+cpu, which only the cpu repack
    # index serves (default PyPI has no +cpu wheel); preinstall it first so the
    # -r cpu.txt row is satisfiable (issue #1241, #1544). torch_backend renders to 'cpu'.
    # cpu.txt also asks bare 'torchvision'/'torchaudio' (no +cpu suffix) — resolving
    # them from default PyPI installs _C built against the non-cpu torch ABI, so
    # torchvision::nms/SGD ops never register and 'vllm --version' dies with
    # 'operator torchvision::nms does not exist' at import (issue #1365 run
    # 41345449621 cpu). Preinstall the ABI-matched +cpu wheels from the SAME index.
    # torchcodec (video decoding backend, `>= 0.14` in cpu.txt) has the same class of
    # bug: the default-PyPI wheel fails `torch.ops.load_library(libtorchcodec_image.so)`
    # against the preinstalled +cpu torch with the generic "Could not load this library"
    # (issue #1365 run 41355299891 cpu) — pull it from the same index too.
    # NB: this preinstall pin MUST track the sha's own cpu.txt torch pin (bumped 2.13→2.14
    # at v0.33.0 3a4d82f5). A lag here re-opens #1544: step 2 `-r cpu.txt` wants the sha's
    # newer torch, which default PyPI cannot satisfy (no +cpu wheel) → 'unsatisfiable'.
    - "uv pip install --system --break-system-packages torch==2.14.0 torchvision torchaudio torchcodec --index-url https://download.pytorch.org/whl/{torch_backend}"
    - "uv pip install --system --break-system-packages -r {src}/requirements/build/cpu.txt --index-strategy unsafe-best-match"
    # vendored Rust frontend (vllm-rs): build_rust.sh precompiles the artifacts so -e . skips cargo
    - "cd {src} && bash tools/build_rust.sh"
    - "cd {src} && VLLM_TARGET_DEVICE=cpu uv pip install --system --break-system-packages --no-build-isolation -e ."
binary: "vllm"
binary_flags: ["--version", "--help"]   # the vllm CLI answers --version (cpu detect) and --help
binary_probe:
  cuda: device   # the cuda/rocm CLI probes the device at startup and fails on a GPU-less runner (CI #106)
  rocm: device
detect:
  # the cuda/rocm builds probe the device on startup and fail on a GPU-less
  # runner (CI #106); the version comes from the package instead
  cuda: "python3 -c 'from vllm import __version__ as v; print(v)'"
  rocm: "python3 -c 'from vllm import __version__ as v; print(v)'"
  cpu: "{binary} --version"
launch:
  cuda: "{binary} serve {model} --host {host} --port {port} --served-model-name {alias} --gpu-memory-utilization 0.90"
  rocm: "{binary} serve {model} --host {host} --port {port} --served-model-name {alias} --gpu-memory-utilization 0.90"
  # on CPU --gpu-memory-utilization is a share of system RAM (0.90 refused to start
  # on a 62 GiB host, CI #98); VLLM_CPU_KVCACHE_SPACE (GiB) sizes the KV cache instead
  cpu: "{binary} serve {model} --host {host} --port {port} --served-model-name {alias}"
env:
  cuda:
    # uv's download HTTP timeout is 30s by default; the big nvidia-cusparse / cudnn
    # wheels on a slow link can trip it mid-extract (network flake on the shared-ci
    # link, not a code fault). Raise it for every uv install so a slow wheel doesn't
    # fail the cell (issue #1568; proven value 180 from the local rocm build).
    UV_HTTP_TIMEOUT: "180"
  rocm:
    # The rocm download phase pulls dozens of amd-torch-device / rocm-sdk-device-gfx*
    # wheels (up to 320MiB each, per-gfx peer); on a slow link the default 30s uv
    # timeout flakes the cell before any compile starts (build1 died on mpmath==1.3.0
    # at UV_HTTP_TIMEOUT=30; build2 cleared every download at 180). Raise it so the
    # device wheels reach the cache warm (issue #1568).
    UV_HTTP_TIMEOUT: "180"
  cpu:
    VLLM_CPU_KVCACHE_SPACE: "4"
    # The cpu build also resolves torch/numpy/psutil from pip on the slow link; keep
    # the same raised uv timeout so a slow wheel can't fail the cell (issue #1568).
    UV_HTTP_TIMEOUT: "180"
health: "GET /health"
alias_mode: flag
container:
  # every cell compiles the pinned sha on the shared devel base for that backend
  # (cuda: nvidia/cuda:13.0.2-devel, rocm: rocm/dev-ubuntu-24.04:7.0-complete,
  #  cpu: ubuntu:24.04) — no upstream vLLM wheel is installed (issue #937)
  cuda:
    apt: [python3-dev]
  rocm:
    apt: [python3-dev]
    # The full FAT list (gfx1030;gfx1100;gfx1101;gfx1102;gfx1151;gfx1200;gfx1201;gfx942)
    # compiles 8 HIP targets and the cold build never fits the 240-min cell timeout
    # (run 41767119317: rocm cancelled at exactly 4h00m #1694) — every rerun stays cold.
    # Trim to the current fleet-level targets (MI300 gfx942, RDNA3 gfx1100/1101, newest
    # RDNA4 gfx1201) so the editable compile clears the wall on a hosted runner. This
    # override is vllm-scoped: other engines keep FAT_GPU_TARGETS.
    gpu_targets: "gfx942;gfx1100;gfx1101;gfx1201"
  cpu:
    apt: [python3-dev, libnuma-dev]
upstream_watch: [pyproject.toml, requirements/cuda.txt, requirements/rocm.txt, requirements/cpu.txt, docs/getting_started/installation/gpu.md, docs/getting_started/installation/cpu.md, docker/Dockerfile.rocm_base]
---

# vLLM

Built from the pinned sha on the shared devel base for the backend, installed into the engine
image's own Python with `uv pip install --no-build-isolation -e .` (the container is the
isolation; nothing is installed on the host).

## Hardware parameters

| Backend | Selection | Notes |
|---|---|---|
| cuda | compile at the pin: `uv pip install --no-build-isolation -e .` with `CMAKE_ARGS=-DCMAKE_CUDA_ARCHITECTURES` and `MAX_JOBS=6` | compute capability >= 7.5, fat arch list `75;80;86;89;90;120`. Six nvcc jobs — vLLM's docs' own "avoid overload" example — so the 16 GiB CI runner is not SIGKILL'd while not being the "much slower" 2-job path |
| rocm | compile at the pin: same editable install with `VLLM_TARGET_DEVICE=rocm` + `PYTORCH_ROCM_ARCH` | gfx942 (MI300), RDNA3 gfx1100/1101, newest RDNA4 gfx1201 (ROCm >= 7.0.2). Trimmed from the 8-target FAT list so the cold compile fits the 240-min cell wall (#1694) |
| cpu | compile at the pin: `VLLM_TARGET_DEVICE=cpu uv pip install --no-build-isolation -e .` | pure Python/C++ CPU build, AVX2/AVX512 or NEON |

There is no macOS GPU backend. `vllm-metal` is a separate project.

## Launch

`vllm serve <hf-id|dir> --host 127.0.0.1 --port 11434 --served-model-name llm-local`.
The default host is `0.0.0.0`, so always pass `--host`. Tune with `--max-model-len`,
`--gpu-memory-utilization`, `--kv-cache-dtype fp8` and `--quantization`. GGUF loading is limited.
Prefer safetensors/AWQ/GPTQ. Routes: `/v1/chat/completions`, `/v1/completions`,
`/v1/models`, `/health`.

## Pitfall: VRAM held by another server

`--gpu-memory-utilization` is a share of **total** VRAM, and vLLM refuses to start
when that much is not free (`Free memory on device cuda:0 (1.31/15.6 GiB) on startup
is less than desired GPU memory utilization`). Even a small value can hit
`torch.OutOfMemoryError` while the CUDA context loads. This was seen on an RTX 4090
Laptop while a llama-server held 14 GB. Stop the other server on the GPU first: llgenie
serves one model at a time on the port. Do not lower the utilization until it fits.
