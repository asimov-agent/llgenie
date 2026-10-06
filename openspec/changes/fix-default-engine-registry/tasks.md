## 1. Fix

- [x] 1.1 `scripts/engine_image.py`: `DEFAULT_REGISTRY` and `REGISTRY` falls back to it; override and empty-value behaviour kept.

- [x] 1.2 Strata launch: `llm-local` added to the config's `aliases`, no `--model-alias`; `alias_mode: config`; params regenerated.

- [x] 1.3 Strata image: `-DSTRATA_PORTABLE=ON` and a setup-format `engine/BUILD.json` (cuda, rocm); params regenerated.

## 2. Tests

- [x] 2.1 `tests/test_engine_skills.py::test_engine_images_default_to_the_published_registry_without_make` (make test-unit); watched it fail before the fix.
- [x] 2.2 `tests/test_install_published.py::test_first_use_pull_works_without_llgenie_registry_live` (live GHCR, docker socket); watched it fail before the fix.
- [x] 2.3 `tests/test_strata_download.py::test_launch_line_is_accepted_by_strata_server_and_serves_llm_local` (Strata's real server.py); watched it fail on the old launch line.
- [x] 2.4 `tests/test_engine_version.py::test_strata_engine_runs_on_avx2_cpus_and_setup_reuses_it`: fails on the published image (32 zmm in ggml_cpu_init, no BUILD.json).
- [x] 2.5 Real start on the AVX2 host (i9-13980HX, RTX 4090 Laptop 16 GB): setup reused the engine, `/v1/models` lists llm-local, "hi" answered at ~57-61 tok/s.
- [x] 2.6 `make test-unit`, `make lint` and `make openspec-validate NAME=fix-default-engine-registry` pass.
