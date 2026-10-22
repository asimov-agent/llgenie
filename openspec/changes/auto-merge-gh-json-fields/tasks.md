# Tasks — auto-merge-gh-json-fields (issue #513)

- [ ] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-gh-json-fields/spec.md`, this checklist
- [ ] 2. `scripts/auto_merge.py`: `PR_VIEW_FIELDS` (one constant, `authorAssociation` gone), `pr_state` joins it, `is_bot_login()` decides the bot rule from the login alone
- [ ] 3. `tests/fixtures/gh-pr-view-fields.json`: gh's real `pr view --json` allowlist, captured from the CLI
- [ ] 4. `tests/test_auto_merge.py`: the field list is locked against that allowlist, the bot-login rule is exercised, and the fake `gh` refuses an unknown field name the way the real CLI does
- [ ] 5. `README.md` + `agent-wiki/2026-10-22-auto-merge-gh-json-fields.md`
- [ ] 6. Verified: `pytest tests/test_auto_merge.py`, `make lint`, `make check-docs`, `make check-workflows`, `make test-unit`, `make openspec-validate NAME=auto-merge-gh-json-fields`, and a real `make auto-merge-explain` against a live PR — results in the PR
- [ ] 7. The next green PR run's `auto-merge` job is GREEN and merges the PR with no human click (the proof the gate works)
