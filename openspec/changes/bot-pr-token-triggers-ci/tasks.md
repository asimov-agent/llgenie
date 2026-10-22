# Tasks — bot-pr-token-triggers-ci (issue #497)

- [x] 1. OpenSpec change: `proposal.md`, `specs/bot-pr-token-triggers-ci/spec.md`, this checklist
- [x] 2. `scripts/architecture_bot.py`: `_gh(..., token=…)`, `publish(..., pr_token=…)`, `PR_TOKEN` read for `gh pr create` with a stderr warning when it is empty
- [x] 3. `.github/workflows/architecture-bot.yml`: `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}` beside the job token
- [x] 4. `tests/test_architecture_bot.py`: the recorded `gh` records the token; issue-call and PR-call tokens differ; the publish step carries both
- [x] 5. `README.md` + `agent-wiki/2026-10-21-bot-pr-token-triggers-ci.md`
- [x] 6. Verified: `pytest tests/test_architecture_bot.py` → 13 passed, `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-dispatch-forms`, `make openspec-validate NAME=bot-pr-token-triggers-ci`, `make test-unit`
