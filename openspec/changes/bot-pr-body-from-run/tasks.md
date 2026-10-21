# Tasks — bot-pr-body-from-run (issue #429)

- [x] 1. OpenSpec change: `proposal.md`, `specs/bot-pr-body-from-run/spec.md`, this checklist
- [x] 2. `scripts/issue_implementer.py`: `pr_title`, `render_pr_body`, `diffstat`, and `open_pr` taking a body file and refusing a missing/thin body before any `gh` call
- [x] 3. `Makefile`: `issue-bot-open-pr` passes `--body-file pr-body.md` (no `--title`/`--wants`); `_implement-issue` asks the agent for the four-part `pr-body.md`
- [x] 4. `.gitignore`: `pr-body.md` is a run input
- [x] 5. `tests/test_bot_pr_body.py` (8 cases) + the two `open_pr` call sites updated in `tests/test_issue_implementer.py`
- [x] 6. `README.md` + `agent-wiki/2026-10-21-bot-pr-body-from-run.md` record the body contract
- [x] 7. Verified: `make test-unit` green, `make check-docs`, `make lint`, `make check-wiring`, `make openspec-validate NAME=bot-pr-body-from-run` green, and `make issue-bot-open-pr` shown refusing a thin body and rendering a real one
