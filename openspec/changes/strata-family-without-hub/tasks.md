# Tasks

- [x] 1. `scripts/strata_models.py::extract()`: describe a family with no `hf` as `"hub": false` (no repo/revision/subdir invented); a family with `hf` keeps the committed key order
- [x] 2. `scripts/model_engine_pick.py`: `strata_serves` matches a repo only when the family has one, `strata_first_shards` skips a Hub-less family, `strata_files` raises a named `ValueError`
- [x] 3. `tests/test_strata_missing_hf.py`: 5 cases — the #416 repro, the committed key order, byte-stability at the pin, the skip, the named refusal
- [x] 4. `README.md` states that a family without a Hub URL is vendored as not Hub-downloadable; `agent-wiki/2026-10-20-strata-family-without-hub.md` records the work with issue #416 and the PR
- [x] 5. Verification: `make check-strata-models` (byte-identical at the pin), `pytest tests/test_strata_missing_hf.py` (5 passed), the same check against Strata HEAD no longer raises `KeyError: 'hf'`, `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=strata-family-without-hub`, `make test-unit`
