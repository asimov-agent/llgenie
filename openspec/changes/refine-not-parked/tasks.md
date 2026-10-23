# Tasks — refine-not-parked (issue #522)

- [x] 1. OpenSpec change: `proposal.md`, `specs/refine-not-parked/spec.md`, this checklist
- [x] 2. `DECIDED_LABELS = ("agent:closed",)`; `REFINED_LABEL` documented as a marker (scripts/issue_implementer.py)
- [x] 3. The refine verdict adds `agent:refined` and `agent:ready` when the issue carries no queue label
- [x] 4. A second refine of an already-refined issue is refused (SystemExit, nothing posted)
- [x] 5. Docstrings / `--json` wording / README: only a close is a decision
- [x] 6. Tests: refined issue is picked; refine queues; closed skipped without a thread read; refined canonical queued; fixtures updated
- [x] 7. Verified: `pytest tests/test_issue_implementer.py tests/test_issue_refiner.py tests/test_bot_claims.py` → 74 passed; `make lint`, `make check-docs`, `make check-workflows`, `make check-wiring`, `make openspec-validate NAME=refine-not-parked`, `make openspec-tasks-check`; `make test-unit` in the PR checks
- [x] 8. `agent-wiki/2026-10-23-refine-not-parked.md` records the change with the issue and PR
