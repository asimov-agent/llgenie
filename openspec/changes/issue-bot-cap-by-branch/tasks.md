# Tasks

- [x] 1. `scripts/issue_implementer.py`: `BOT_BRANCH_PREFIX` + `PR_LIST_LIMIT`; `count()` lists PRs and counts today's `agent/issue-*` ones (never a login)
- [x] 2. `tests/test_issue_implementer.py`: the fake `gh` answers `pr list`; the numerator test asserts the query; a new case proves a human's PR and another day's PR do not count
- [x] 3. `README.md` states that the cap counts the dispatcher's own branch shape; `agent-wiki/2026-10-20-issue-bot-cap-by-branch.md` records the work with issue #409 and the PR
- [x] 4. Verification: `pytest tests/test_issue_implementer.py` (29 passed), `python3 scripts/issue_implementer.py count --repo asimov-agent/llgenie --today 2026-10-19`, `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=issue-bot-cap-by-branch`, `make test-unit`
