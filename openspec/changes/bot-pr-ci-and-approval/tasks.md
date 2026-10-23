# Tasks — bot-pr-ci-and-approval (issues #497, #529)

- [x] 1. OpenSpec change: `proposal.md`, `specs/bot-pr-ci-and-approval/spec.md`, this checklist
- [x] 2. `scripts/architecture_bot.py`: `_gh(..., token=)` / `_gh_retry(..., token=)` pass an override through the child environment, and `publish()` creates the PR with `PR_TOKEN` while the issue keeps the job token
- [x] 3. `.github/workflows/architecture-bot.yml`: `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}` on the publish step
- [x] 4. `scripts/auto_merge.py`: `try_approve()` accepts this repo's own bot author (`_is_bot`), still refusing a stranger
- [x] 5. `tests/test_architecture_bot.py` (fake `gh` records the credential per call) + `tests/test_auto_merge.py` (bot author approved, stranger still refused)
- [x] 6. `README.md` + `agent-wiki/2026-10-22-bot-pr-ci-and-approval.md`
- [x] 7. Verified: `pytest tests/test_auto_merge.py tests/test_architecture_bot.py` → 50 passed; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=bot-pr-ci-and-approval`, `make test-unit` → 5022 passed, 6 deselected
- [x] 8. PR opened against `asimov-agent/llgenie:main` closing #497 and #529
