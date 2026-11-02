# Tasks — auto-merge-skip-stacked-base (issue #963)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-skip-stacked-base/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `decide()` skips `baseRefName != "main"`, `baseRefName` in
         `PR_VIEW_STATE_FIELDS`, and the run summary names the base as the reason
- [x] 3. `scripts/auto_merge.py`: `stacked-merged` command reports author + head sha + check-runs count
- [x] 4. `.github/workflows/auto-merge.yml`: the scheduled recheck runs the stacked-base report
- [x] 5. `tests/test_auto_merge.py`: the negative control (non-main base armed → merger skips) + detector test
- [x] 6. `docs/BOTS.md` one-line rule + README/Makefile help + `agent-wiki` note + `docs/changes.d` fragment
- [x] 7. Verified: targeted pytest green, `make lint`, `make check-wiring`, `make check-docs`,
         `make check-workflows`, `make openspec-validate NAME=auto-merge-skip-stacked-base`,
         loop gate (`make test-unit`)
