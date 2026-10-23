# Tasks — auto-merge-wait-for-approval (issue #531)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-wait-for-approval/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `wait_for_merge_state()` (bounded poll), `_clear_review()` decides from it, and the deferral names the wait instead of `None`
- [x] 3. `tests/test_auto_merge.py`: fake `gh` can hold `BLOCKED` for N reads after the approval; two cases (settles → merged, never settles → real reason)
- [x] 4. `README.md` + `agent-wiki/2026-10-22-auto-merge-wait-for-approval.md`
- [x] 5. Verified: `pytest tests/test_auto_merge.py` → 36 passed; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=auto-merge-wait-for-approval`, `make test-unit` → 5022 passed, 6 deselected
- [x] 6. PR opened against `asimov-agent/llgenie:main` closing #531
