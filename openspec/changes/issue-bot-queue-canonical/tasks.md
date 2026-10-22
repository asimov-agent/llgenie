# Tasks — issue-bot-queue-canonical (issue #521)

- [x] 1. OpenSpec change: `proposal.md`, `specs/issue-bot-queue-canonical/spec.md`, this checklist
- [x] 2. `scripts/issue_implementer.py`: `QUEUE_LABELS` / `ISSUE_REF` constants, `cited_issues()`, `_issue_meta()`, `queue_canonical()`, and the close path calling it (dry included)
- [x] 3. `tests/test_issue_implementer.py`: fake `gh` answers the `--json state,labels` lookup; four new cases (queues the canonical, leaves closed/decided/queued/self alone, unreadable reference still closes, dry mutates nothing)
- [x] 4. `README.md` + `agent-wiki/2026-10-22-issue-bot-queue-canonical.md`
- [x] 5. Verified: `pytest tests/test_issue_implementer.py tests/test_bot_claims.py` → 51 passed; `make test-unit` → 5018 passed, 6 deselected; a real `apply-verdict --dry` against the live repo printed the queue decisions; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=issue-bot-queue-canonical`
- [x] 6. PR opened against `asimov-agent/llgenie:main` closing #521
