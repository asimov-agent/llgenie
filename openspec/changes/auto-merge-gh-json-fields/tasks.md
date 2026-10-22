# Tasks — auto-merge-gh-json-fields (issue #513)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-gh-json-fields/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `PR_VIEW_FIELDS` (one constant, `authorAssociation` gone), `pr_state` joins it, `is_bot_login()` decides the bot rule from the login alone
- [x] 3. `tests/fixtures/gh-pr-view-fields.json`: gh's real `pr view --json` allowlist, captured from the CLI
- [x] 4. `tests/test_auto_merge.py`: the field list is locked against that allowlist, the bot-login rule is exercised, and the fake `gh` refuses an unknown field name the way the real CLI does
- [x] 5. `README.md` + `agent-wiki/2026-10-22-auto-merge-gh-json-fields.md`
- [x] 6. Verified: `python -m pytest tests/test_auto_merge.py` → 31 passed; `make test-unit` → 5039 passed, 6 deselected; `make lint`, `make check-docs`, `make check-workflows`, `make check-wiring` green; `make openspec-validate NAME=auto-merge-gh-json-fields` valid; `make auto-merge-explain PR=511 REPO=asimov-agent/llgenie` → real `gh`, real verdict
- [x] 7. PR opened against `asimov-agent/llgenie:main` closing #513, with the bootstrap note (a `workflow_run` workflow runs the `main` copy, so the fix lands by one manual merge; the next green PR run is the end-to-end proof and is recorded on the PR)
