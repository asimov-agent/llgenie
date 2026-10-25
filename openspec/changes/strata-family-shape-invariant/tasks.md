# Tasks

- [x] 1. `scripts/strata_models.py`: add `family_shape_problems()` — a family is Hub-hosted (repo + revision + subdir, no `hub` key) or explicitly not-Hub (`hub: false`, no repo), never both, never neither; `subdir` may be `""`
- [x] 2. `strata_models.py check`: name a malformed committed map by family and defect instead of only reporting a diff; the pinned byte comparison stays
- [x] 3. `tests/test_strata_missing_hf.py`: replace the v0.1.43 snapshot test with the invariant, the both-pin case, the defect cases, the extraction derivation and the `check` message
- [x] 4. `tests/test_strata_download.py` (live tier): read a Hub-less family's shape instead of `KeyError` on `repo`, and derive the not-Hub set from the fetched pinned `setup.py`
- [x] 5. `openspec/changes/strata-family-without-hub`: repoint the scenario whose test this change replaces, so no `- **Test:**` line names a deleted test
- [x] 6. Prove the fix: the old test fails on a v0.2.4-shaped map (`nvfp4 unexpectedly marked not-Hub`) and the new tests pass on both v0.1.43 and v0.2.4
- [x] 7. `README.md` documents the invariant, the `check-strata-models` message and the derived set; `agent-wiki/2026-10-25-strata-family-shape-invariant.md` records the work with the issue and the PR
- [x] 8. Verification: `python3 scripts/unit_tests.py run` (5182 passed, 6 deselected — the aggregator `make test-unit` runs; no Docker daemon here, so the container wrapper could not be used), `python3 scripts/lint_linefeeds.py`, `make check-wiring`, `make check-docs`, `make openspec-tasks-check NAME=strata-family-shape-invariant`
