# Tasks — engine-bump-regen-guard (#2506)

- [x] `_porcelain_paths()` helper: parse `git status --porcelain` paths (rename-aware), reused by `_regen_guard`
- [x] `_regen_guard` snapshots the porcelain set before regen and guards only paths new after it
- [x] The §"Regen guard + changed-engines scoping" fakes become call-sequence-aware (first status read = baseline) and keep their original verdicts
- [x] New regression test `test_regen_guard_ignores_a_prior_engine_s_dirtiness` proves the multi-engine shape
- [x] `pytest tests/test_engine_bump.py -q` green; `make openspec-validate NAME=engine-bump-regen-guard` exits 0
- [x] The commit message carries `closes #2506` and `pytest tests/test_engine_bump.py` is green at this commit (75 passed) — the PR is opened from this branch against upstream main
