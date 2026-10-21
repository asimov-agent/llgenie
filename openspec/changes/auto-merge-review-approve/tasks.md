# Tasks — auto-merge-review-approve (issue #491)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-review-approve/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `review_blocked`, `token_login`, `try_approve` (other identity only, never a self-approval, never a stranger), the deferral comment once per head SHA, and the `explain` subcommand
- [x] 3. `Makefile`: `auto-merge` gains `APPROVE=1`; new `auto-merge-explain`; `.PHONY`; help lines
- [x] 4. `.github/workflows/ci.yml`: the job sets `APPROVE: "1"` (still `secrets.BUMP_TOKEN`)
- [x] 5. `tests/test_auto_merge.py`: approve-then-merge, no self-approval, no stranger approval, no approval for other blockers, one deferral comment per head, `explain` writes nothing, the workflow's `APPROVE`, the new target's wiring
- [x] 6. `AGENTS.md` + `README.md` + `agent-wiki/2026-10-21-auto-merge-review-approve.md`: the policy and its limits
- [x] 7. Verified: `pytest tests/test_auto_merge.py` → 23 passed, `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=auto-merge-review-approve` green, `make test-unit` green (numbers in the PR)
