# Tasks: engine-skill-strata-2868

## 1. Reproduce and re-derive
- [x] 1. Read the failing cuda/rocm configure output from the bump-wave runs and pin the root
  cause to `setup.get_llama_cpp() -> None` + `-DSTRATA_GGML_DIR=None` (done in the proposal;
  evidence: `engine-build-strata-cuda` job 133520076013, CMakeLists.txt:603 →
  cmake/strata_ggml.cmake:56).
- [x] 2. Verify the v0.2.15 API surfaces the remaining recipe calls need: `cmake_build`,
  `find_nvcc`, `source_version`, `source_hash`, `ENGINE_SOURCES`, `gguf_choice`,
  `serve/server.py`, vendored `third_party/strata-ggml` (146 files).

## 2. Skill re-pin + recipe re-derivation
- [x] 3. `skills/engines/strata/SKILL.md`: `ref`/`version` `v0.2.15`, `pinned`
  `0a80d5e5ed2f3c7602efb9d697be71a6321abf62`, `verified` 2026-11-17; remove
  `setup.get_llama_cpp()` and `-DSTRATA_GGML_DIR=` from the cuda and rocm install commands;
  record the vendored-ggml change note in the skill body; `launch` gains `--api-key none`
  (v0.2.15 arms `$STRATA_API_KEY`/config keys by default; the flag takes the server's
  `explicit_no_key` path even against a stray env key).

## 3. Model table follows the engine's per-size overrides
- [x] 3b. `scripts/strata_models.py::extract` carries per-model `quant` and `revision` from the
  pinned `MODELS`; `scripts/model_engine_pick.py` uses them in `strata_files()` (Hub name) and
  `strata_plan()` (per-model revision); `scripts/engine_source_guard.py` follows the build
  signal to `setup.cmake_build(`. Proven: `make sync-strata-models` + `make check-strata-models`
  0 problems, v31 names resolve at `UNSLOTH_V31_REVISION`.
- [x] 3c. `tests/test_strata_download.py` flips the v0.2.11-era refusals the pin lifted: the
  unsloth `UD-IQ1_M` set is now a strata model (acceptance + never-planned) and a new test
  proves a complete `UD-IQ1_M` set is reused; the "cannot run"/"pre-launch refuses" slots use
  `IQ1_S`, absent from the pinned `MODELS`. Targeted run: 41 passed, 0 failed.

## 4. Companions + gates
- [x] 4. `make generate-engine-params ENGINE=strata`; confirm the Dockerfiles and
  `params/strata.json` carry `v0.2.15` and the llama-free recipe.
- [x] 5. Engine gates `check-engine-params` / `check-engine-source` / `check-engine-capabilities`
  / `check-engine-coverage` / `skills-validate` / `check-strata-models` rc=0; host launchers
  regenerated so `check-engine-launchers` matches the committed params. `tests/test_engine_skills.py`
  and `docs/ENGINES.md` carry no strata version literal (verified by grep), so the pin needs no
  follow there.

## 5. Docs pair + validate
- [x] 6. `agent-wiki/2026-11-17-engine-skill-strata-2868.md` +
  `docs/changes.d/2026-11-17-engine-skill-strata-2868.md`; `make changes-index` +
  `make check-docs` rc=0; `make openspec-validate NAME=engine-skill-strata-2868` rc=0.

## 6. Ship verification
- [x] 7. The branch carries the full companion set proven on the committed tree:
  `make test-unit` rc=0 (3963 passed, 13478 deselected, 1052.01s).
  Push/PR and the PR's green `engine-build-strata-cuda` run id (issue AC 1) are recorded on
  the PR/issue, not a task here.
