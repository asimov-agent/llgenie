# Tasks — auto-merge-workflow-run (issue #493)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-workflow-run/spec.md`, this checklist
- [x] 2. `.github/workflows/auto-merge.yml`: `workflow_run` on `CI` completion, base-branch checkout, PR resolution from the run, `make auto-merge` with `secrets.BUMP_TOKEN`
- [x] 3. `ci.yml`: the `auto-merge` job removed, with a comment naming where it went; `tests/test_ci_images.py` skip-guard exception removed
- [x] 4. `scripts/auto_merge.py`: `_require_token` (exit 2, names the defect) and `TRUSTED_HEAD_OWNERS` (a third-party fork head is deferred)
- [x] 5. `tests/test_auto_merge.py`: the workflow_run trigger/guards, the base checkout, the PR resolution, the empty-PAT step, the CLI token guard, the third-party fork deferral, `ci.yml` no longer carrying the job
- [x] 6. `README.md` + `agent-wiki/2026-10-21-auto-merge-workflow-run.md`
- [x] 7. Verified: `pytest tests/test_auto_merge.py tests/test_ci_images.py` → 53 passed, `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=auto-merge-workflow-run`, `make test-unit` — results in the PR
