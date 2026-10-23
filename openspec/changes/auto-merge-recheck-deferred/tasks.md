# Tasks — auto-merge-recheck-deferred (issue #545)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-recheck-deferred/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `deferred_for_head()` + `recheck()` (same `run()`, current-head marker only, `--max-prs`) and the `recheck` subcommand
- [x] 3. `Makefile`: `auto-merge-recheck REPO= [MAX=5] [DRY=1]`
- [x] 4. `auto-merge.yml`: `schedule: */30 * * * *` + the `recheck` job (BUMP_TOKEN, APPROVER_TOKEN); `merge` stays `workflow_run`-only
- [x] 5. `tests/test_auto_merge.py`: fake `gh` answers `pr list` and per-PR `pr view`; four cases (retried+merged, stale head, no marker, workflow wiring)
- [x] 6. `README.md` + `agent-wiki/2026-10-23-auto-merge-recheck-deferred.md`
- [x] 7. Verified: `pytest tests/test_auto_merge.py` → 41 passed; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=auto-merge-recheck-deferred`, `make openspec-tasks-check`; `make test-unit` in the PR checks
- [x] 8. PR opened against `asimov-agent/llgenie:main` closing #545
