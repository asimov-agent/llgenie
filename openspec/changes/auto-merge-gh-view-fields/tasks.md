# Tasks — auto-merge-gh-view-fields (issue #513)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-gh-view-fields/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `PR_VIEW_STATE_FIELDS` / `PR_VIEW_COMMENT_FIELDS` / `PR_VIEW_FIELDS` in one place, `pr_state` and `pr_comments` built from them, `authorAssociation` removed, `_is_bot` decides the bot rule from the login
- [x] 3. `tests/fixtures/gh-pr-view-fields.json`: the real `gh pr view --json __probe__` allowlist with its command and version
- [x] 4. `tests/test_auto_merge.py`: field-list lock, `pr_state` argv pinned to the constant, login-only bot rule (App bot and `[bot]`), `authorAssociation` gone from the state fixtures
- [x] 5. `README.md` + `agent-wiki/2026-10-22-auto-merge-gh-view-fields.md`: the field-allowlist rule and its proof
- [x] 6. Verified: full unit suite `5040 passed, 6 deselected` (scripts/unit_tests.py, Python 3.11); `pytest tests/test_auto_merge.py` → 32 passed; `make auto-merge-explain PR=511 REPO=asimov-agent/llgenie` → real verdict; `openspec validate auto-merge-gh-view-fields` → valid; `make lint` script, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-tasks-check NAME=auto-merge-gh-view-fields` green
