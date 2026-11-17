# OpenSpec change: engine-skill-strata-2868

## Why

`engine-build-strata-cuda` fails on the v0.2.15 bump (superseded PR #2859, head `f9e8ed230`):
`CMake Error at cmake/strata_ggml.cmake:56 (add_subdirectory): add_subdirectory given source
"/opt/llgenie/engines/strata/src/None/ggml" which is not an existing directory`. The literal
`None` proves the cause: our install recipe feeds the build `-DSTRATA_GGML_DIR=` + the return of
`setup.get_llama_cpp()`, but at v0.2.15 that call is a vestigial shim ("Nothing is downloaded
any more" — `setup.py:3829`) that returns `None`. Strata v0.2.15 vendors its ggml tree in
`third_party/strata-ggml` (146 files; `STRATA_GGML_DIR` became an optional override, empty by
default), so the llama.cpp plumbing our recipe carries from the v0.2.11 era is dead weight that
now actively breaks configure. The rocm cell fails the same way (`-DSTRATA_GGML_DIR` in the hip
recipe). main still pins v0.2.11.

## What Changes

- Re-pin the strata engine skill to `v0.2.15` (`pinned: 0a80d5e5ed2f3c7602efb9d697be71a6321abf62`).
- Re-derive the cuda and rocm install recipes: drop `setup.get_llama_cpp()` and the
  `-DSTRATA_GGML_DIR=` define from both inline build commands, letting cmake take ggml from the
  vendored `third_party/strata-ggml` (the upstream default at v0.2.15). Every other define
  (`STRATA_ENABLE_CUDA/HIP`, `STRATA_BUILD_TESTS=OFF`, `STRATA_PORTABLE=ON`, arch lists,
  `CMAKE_CUDA_COMPILER`, the `engine/BUILD.json` stamp) is verified present in the v0.2.15
  `setup.py` build path and stays.
- Regenerate the companion set from the skill in one pass (`make generate-engine-params
  ENGINE=strata`): the strata Dockerfiles and `containers/engines/params/strata.json` follow the
  new pin and recipes.
- Carry the engine's per-size Hub overrides through the vendored model table: v0.2.15's `MODELS`
  gives some sizes their own Hub `quant` name (key `UD-IQ4_XS-v31` ships files named
  `UD-IQ4_XS`) and their own revision (the v31 set lives at `UNSLOTH_V31_REVISION`).
  `scripts/strata_models.py::extract` records both per model; `scripts/model_engine_pick.py`
  builds Hub paths from the `quant` and resolves the revision per model, so every planned file
  name is verifiable against the pinned Hub tree (`make sync-strata-models` /
  `check-strata-models` rc=0).
- `launch` chooses key-free serving explicitly: v0.2.15 `serve/server.py` honours
  `$STRATA_API_KEY` / a config `api_key` by default, so the launch line passes `--api-key none`
  (the server's `explicit_no_key` path, which also overrides a stray env key). llgenie serves
  inside the host's local boundary like an unauthenticated `llama-server`.
- Flip the test expectations where the engine changed: `tests/test_strata_download.py` asserted
  that unsloth's `UD-IQ1_M` set is REFUSED (true at v0.2.11, #643); v0.2.15 ships it, so those
  assertions flip to acceptance, and the "a file Strata cannot run" slot uses `IQ1_S`, which the
  pinned `MODELS` does not carry. `scripts/engine_source_guard.py` follows the build signal from
  `setup.get_llama_cpp(` to `setup.cmake_build(`.
- Follow the pin in the real-tree strata test assertions and docs wording.

## Impact

- Affected specs: `strata-engine-build` (ADDED requirements: vendored-ggml builds at the pin;
  per-size Hub overrides in the vendored model table; key-free launch)
- Affected code: `skills/engines/strata/SKILL.md`, `containers/engines/dockerfiles/strata/*`,
  `containers/engines/params/strata.json`, `scripts/strata_models.py`,
  `scripts/model_engine_pick.py`, `scripts/engine_source_guard.py`, `data/strata_models.json`,
  `tests/test_strata_download.py`
- No engine image is built on the host; the PR's engine-build cuda cell is the live proof
  (rocm stays hardware-parked per the standing ROCm rule).
