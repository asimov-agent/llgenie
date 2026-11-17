# 2026-11-17 — strata engine skill re-pin v0.2.11 → v0.2.15 (#2868)

## What was verified against the issue

- **Root cause measured, not guessed.** The v0.2.15 bump's cuda cell (superseded PR #2859,
  run 43909735496, job 133520076013) fails at
  `CMake Error at cmake/strata_ggml.cmake:56 (add_subdirectory): add_subdirectory given source
  "/opt/llgenie/engines/strata/src/None/ggml"`. The literal `None` is the proof: the recipe
  passed `-DSTRATA_GGML_DIR=` + `setup.get_llama_cpp()`, and at v0.2.15 that function is a
  vestigial shim ("Nothing is downloaded any more", `setup.py:3829`) that returns `None`.
  The rocm cell carries the same dead define.
- **v0.2.15 vendors ggml.** `third_party/strata-ggml` (146 files) exists at the tag and
  `cmake/strata_ggml.cmake` treats `STRATA_GGML_DIR` as an optional override, empty by default.
- **API surfaces re-checked at the pin**: `cmake_build`, `find_nvcc`, `source_version`,
  `source_hash`, `ENGINE_SOURCES`, `gguf_choice`, `serve/server.py`, `requirements.txt` all
  present; every remaining define (`STRATA_ENABLE_CUDA/HIP`, `STRATA_BUILD_TESTS=OFF`,
  `STRATA_PORTABLE=ON`, arch lists, `CMAKE_CUDA_COMPILER`, `GPU_TARGETS`) verified in the
  v0.2.15 `setup.py` build path before the recipes were trimmed.
- Tag: `v0.2.15` → tag object `0a80d5e5ed2f3c7602efb9d697be71a6321abf62`.

## Key decisions

- The cuda/rocm install commands drop `setup.get_llama_cpp()` and `-DSTRATA_GGML_DIR=`; cmake
  takes ggml from the vendored tree (the upstream default). No other define changed.
- `scripts/engine_source_guard.py`'s strata build signal was literally `get_llama_cpp\(`
  ("Strata compiles llama.cpp this way") — stale by construction at v0.2.15. Replaced with
  `setup\.cmake_build\(`, the driver the engine actually compiles with. The guard must describe
  the real build, not the old one.
- `data/strata_models.json` re-synced from `setup.py` at the new pin (`make sync-strata-models`),
  drift check green (`make check-strata-models` rc=0).
- Historical `v0.2.11` mentions in `test_engine_bump.py`, `test_strata_missing_hf.py`,
  `test_engine_detect_safety.py` docstrings are narratives about past bumps; invariant tests
  untouched.

## Current status

Branch `feat/engine-skill-strata-2868`; PR opens issue #2868. The live proof for AC 1 is the
PR's own `engine-build-strata-cuda` run (the host does not build engine images; rocm stays
parked per the standing ROCm rule).
