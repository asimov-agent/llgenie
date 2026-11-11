# Hardware probes → build parameters, and the per-engine SKILL.md shape

Reference for building/serving local-LLM inference engines per hardware. Probe
with the REAL system tool, map to a parameter, and make the flag conditional on
whether the probe actually produced a value.

## Probe → parameter map

| Backend | Probe(s) | Derived param | Notes |
|---|---|---|---|
| cuda | `nvidia-smi --query-gpu=compute_cap` (e.g. `8.9`) | `-DCMAKE_CUDA_ARCHITECTURES=89` / `TORCH_CUDA_ARCH_LIST=8.9` | join the two digits `X.Y`→`XY`; CPU-only source builds should omit (drop the flag) so the default/baseline applies |
| cuda | `nvidia-smi --query-gpu=memory.total` | VRAM budget (`card_gb`) → tree/quant choice | 16 GB NVIDIA → Prism fork + low-bit quants; > 24 GB → upstream; GPU VRAM, not system RAM, is the card RAM on an NVIDIA card |
| cuda | CUDA toolkit version (`nvcc --version`) | CUDA wheel selector (`cu12x` index URL), min compute capability gate | each engine lists its supported arch/version range |
| rocm | `rocminfo`/`hipcc` GPU name (`gfx90a`, `gfx1100`, …) | `AMDGPU_TARGETS`/`GPU_TARGETS`/`PYTORCH_ROCM_ARCH=gfx…` | only for engines that HAVE a ROCm backend; older cards often need a flag override (`HSA_OVERRIDE_GFX_VERSION`) |
| metal | macOS + `uname -m`/`sysctl hw.machinetype` in {arm64, aarch64} | `GGML_METAL=ON`-family flags; `sysctl iogpu.wired_limit_mb` for unified-memory headroom | macOS-only by construction; Intel macOS has no Metal path in scope |
| cpu | none (fallback), or CPU feature flags | `GGML_NATIVE=OFF` for a portable baseline | portable = reusable across CI runners; `-march=native` SIGILLs on a different CPU |
| any | `nproc`/`sysctl -n hw.ncpu` | `-j` build jobs | macOS has no `nproc`; CI passes BUILD_JOBS so a container cgroup cannot shrink it |

The backend is chosen in order: env override seam → macOS+Apple-Silicon(Metal) →
NVIDIA GPU+nvcc(CUDA) → CPU fallback. Add ROCm only when rocminfo/hip are
present AND no NVIDIA GPU. Seams (e.g. `LLAMA_BACKEND`, `LLAMA_RAM_BYTES`) let
CI pin a specific tree+backend the host card cannot run.

## Per-engine SKILL.md front-matter shape (consumed by the install runner)

A machine-readable `---` block each engine definition carries, resolved against
the HARDWARE above. Keep the runner + a validator that asserts every engine in
the registry has a parseable, valid skill:

```yaml
---
engine: llama.cpp
repo: https://github.com/ggml-org/llama.cpp
ref: master              # or release tag; track at its latest commit
backends: [cuda, rocm, metal, cpu]   # only what the engine really supports
build:                     # per-backend (cpu shown)
  cpu:
    cmake_flags: ["-DGGML_NATIVE={native}", "-DGGML_CUDA=OFF", "-DGGML_METAL=OFF"]
  # cuda: cmake_flags: ["-DGGML_CUDA=ON", "-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}"]
  #    # cuda_arch dropped when no GPU (unsatisfied placeholder disappears)
  # rocm: cmake_flags: ["-DGGML_HIP=ON", "-DGPU_TARGETS={gfx_target}"]
target: llama-server
binary: "{src}/{build}/bin/llama-server"
serve: "{binary} --server -m {model} --alias {alias} --port {port}"
health: /health
version_cmd: "{binary} --version"
servable: true          # false for browser/library-only engines
server_placeholders: [port, model, alias, src, build, venv, cuda_arch, gfx_target, native]
watch: [CMakeLists.txt, ggml/CMakeLists.txt, docs/build.md]
---
```

- Unknown placeholders fail validation; every listed backend must have a build
  recipe. `servable: false` engines get no health/endpoint assertions.
- Keep the legacy-option alias note (see map above): llama.cpp's `LLAMA_CUBLAS`
  → `GGML_CUDA`, `LLAMA_HIPBLAS` → `GGML_HIP`. Verify against the live fork.
- `watch` lists the upstream files whose change invalidates the skill (drift
  watcher).
