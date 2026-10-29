# Every engine × arch cell that claims a source build must have one (#615)

**Issue:** #615 · **PR:** opened from `fix/615-engine-source-cells` · **Task:** `t_6eacbeea`
**Split out of this change (each linked both ways):** #936 ollama ×4, #937 vllm ×3,
#938 sglang/cuda, #939 tensorrt-llm/cuda.

## Decision taken

The refinement left the scope open: convert the **five mislabelled cells** (the author's own "real
remaining work", comment 2026-10-25T11:07Z) or all **14** non-source cells. This change takes the
five. The nine honestly-labelled `prebuilt: true` cells are nine multi-hour builds whose cost must be
measured *before* the sweep enables them; each engine is filed as its own linked issue rather than
folded into this one (AGENTS.md: one objective per PR, out-of-scope work is its own issue).

| cell | state before | what this change does |
|---|---|---|
| `freetoken/cuda` | `prebuilt: false`, PyPI wheel `freetoken[accel]==0.2.1` | **converted**: clone at `ba31db2e` + upstream `setup.py` (its own CUDA fat arch list, no wheel) |
| `mlx/cpu`, `mlx/cuda` | `prebuilt: false`, PyPI wheels | **converted**: `ml-explore/mlx` @ `1f8e74e3` (tag v0.32.2) built from its own tree — `MLX_BUILD_CUDA=ON` for the cuda cell, `-DMLX_CUDA_ARCHITECTURES` from the shared fat list, cuDNN dev headers — then `mlx-lm` from its pinned tree |
| `tensorfold/cuda` | `prebuilt: false`, release archive | **converted**: the pin *is* a buildable Zig project (`build.zig`, `.zig-version` 0.17.0); `zig build -Dnvcc=… -Dsm=80,86,120,121` (upstream's own `release_sms`) with the compiler from PyPI `ziglang`; no archive is downloaded |
| `litert/cpu` | `prebuilt: false`, PyPI wheel | **dated decision, keeps its tracked entry**: the wheel is a Bazel `py_wheel` over a Git-LFS `prebuilt/<os>/libLiteRt.so` (upstream-compiled core); `bazel build //python/litert_lm_cli:wheel` dies in 92 s at repository mapping with 4.5 GB of Bazel cache; the C++ `//runtime/engine:litert_lm_main` is a different CLI than `litert-lm serve` |

`litert/cpu` does **not** flip to `prebuilt: true`: in this generator that flag means "the image
starts `FROM` the engine's official image", and LiteRT has none — the flag would emit an image with
no engine in it. The honest form for a pip-installed engine is the skill's dated decision plus the
tracked `KNOWN_NOT_SOURCE` entry, which is what the gate prints.

## What was measured, not assumed

- `freetoken/cuda`: in `llgenie/base-cuda` (CUDA 13.0.2 devel) the clone + `uv pip install
  --no-build-isolation -e '.[accel]'` compiles the extensions; the built image's detect answers
  `installed freetoken version 0.2.1` (`make test-engine-stage ENGINE=freetoken ARCH=cuda TEST=detect`
  → 3 passed).
- `mlx`: mlx's `CMakeLists.txt` requires BLAS **and** `lapacke.h` (`find_path`) and CPython headers
  for the bindings, and its CUDA backend additionally needs `cudnn.h` (`cmake/FindCUDNN.cmake`) and an
  explicit `MLX_CUDA_ARCHITECTURES` — without a GPU in the build image `__nvcc_device_query` fails with
  `Can not get native CUDA arch, must set MLX_CUDA_ARCHITECTURES`. Under `--no-build-isolation`
  `mlx-lm` needs `setuptools-scm` on the env or `mlx_lm/_version.py` is never written and every
  `mlx_lm.*` import dies with `ModuleNotFoundError: No module named 'mlx_lm._version'`. The cpu cell
  built and its detect answers `installed mlx-lm 0.32.2 mlx 0.32.2.dev20261029+1f8e74e3f`
  (`make test-engine-stage ENGINE=mlx ARCH=cpu TEST=detect` → 3 passed).
- `tensorfold`: `c425f4cc…` in the skill is the **annotated tag object** of v1.1.6 (the commit is
  `eea9dc9c…`); git peels it, so the pinned checkout works. `ziglang` on PyPI installs
  `/usr/local/bin/python-zig`, not `zig`, so the recipe links it to `zig` before `zig build` (measured:
  `bash: line 1: zig: command not found` without the link). Its fatbins are compiled by `nvcc` from
  `zig CUDA kernels` — the build spends minutes per kernel in `ptxas`.
- `litert`: `bazel 7.6.1` from the repo's `.bazelversion` at pin `bda6248` → `ERROR: … file
  '@rules_cc//cc:extensions.bzl' does not contain symbol 'compatibility_proxy_repo'`, `elapsed_s=92`,
  `4.5G /root/.cache/bazel`; the wheel's runtime is a Git-LFS pointer object.

## Status

Gates: `make generate-engine-params ENGINE=<id>` per converted engine, `make check-engine-source`
(21 of 22 `prebuilt: false` cells run their own build; `litert/cpu` is the one tracked exception),
`make check-engine-params`, `make check-engine-coverage`, and per-cell
`make build-engine ENGINE=<id> ARCH=<arch>` + `make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=detect`.

Verified on this host: `freetoken/cuda` and `mlx/cpu` built from source and their binaries answered
detect; `mlx/cuda` and `tensorfold/cuda` are compiled by the same recipes in CI's `engine-image-*`
jobs. No cell builds from a wheel, a release archive or an upstream engine image.
