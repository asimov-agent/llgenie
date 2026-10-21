# Tasks

- [x] 1. `openspec/changes/issue-bot-manual-pick` — proposal + spec (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before any code
- [x] 2. `.github/workflows/issue-bot.yml` — `issue_number` optional (`required: false`, `default: ""`) with a description and header paragraph saying a blank run picks the oldest `agent:implement` issue itself
- [x] 3. `README.md` — the generated dispatch table row and the issue-bot section state the blank-means-pick contract
- [x] 4. `tests/test_issue_bot_manual_pick.py` — the form (not required, empty default, description), the blank path (`FORCE_ISSUE` empty → no `--force-issue` → `force_issue=None`), the pinned path (`1234` → `--force-issue 1234`), and the header/README agreement with `check_dispatch_forms` green
- [x] 5. `agent-wiki/2026-10-21-issue-bot-manual-pick.md` — the work record, referencing issue #472 and its PR
- [x] 6. Verified: `make test-unit` green with the new file, `make check-dispatch-forms`, `make check-wiring`, `make check-docs`, `make lint`, `make openspec-validate NAME=issue-bot-manual-pick`, `make openspec-tasks-check` all exit 0 (`make test-unit`: 4969 passed, 6 deselected, 1036 s)
