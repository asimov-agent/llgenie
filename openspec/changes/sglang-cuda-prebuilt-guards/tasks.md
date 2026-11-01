# Tasks — sglang-cuda-prebuilt-guards

- [x] 1. `scripts/engine_skills.py::validate`: a cuda backend marked `container.cuda.prebuilt: true` no longer fires the "no install steps for backend cuda" error — the validator shares the renderer's `if prebuilt: steps=[]` special-case (`(container_spec(s, b) or {}).get("prebuilt")`).
- [x] 2. `tests/test_engine_skills.py::test_sglang_cuda_install_uses_uv_not_pip` retargeted to assert BEHAVIOUR (prebuilt → zero install steps + validator-clean; source → uv-not-pip).
- [x] 3. `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`: sglang/cuda asserts it starts FROM `lmsysorg/sglang:v0.5.22` with no install steps; sglang/rocm still compiles.
- [x] 4. `tests/test_engine_source_guard.py::test_the_census_matches_the_committed_params`: census moves to 29 source / 2 prebuilt (sglang/cuda + tensorrt-llm/cuda).
- [x] 5. The four previously-red engine suites pass: `python3 -m pytest tests/test_engine_skills.py tests/test_engine_skill_gap.py tests/test_engine_source_guard.py tests/test_registry_sync_trend.py` → 198 passed, and `python3 scripts/engine_skills.py validate --registry tests/fixtures/models.json` exits 0.
- [x] 6. `make skills-validate` is green (the CLI validator no longer flags sglang/cuda).
- [x] 7. `make linux/unit` (the full hermetic suite) is GREEN at the PR head — run proving it named in the PR body.
- [x] 8. OpenSpec `tasks.md` all ticked, `make openspec-validate NAME=sglang-cuda-prebuilt-guards` exits 0.
