# Tasks — bot-implement-in-place (issue #426)

- [x] 1. OpenSpec change: `proposal.md`, `specs/bot-implement-in-place/spec.md`, this checklist
- [x] 2. `Makefile` `_implement-issue`: the container contract as a hard rule (edit `/repo` in place, no git worktree, no commit/push)
- [x] 3. `tests/test_bot_in_place.py`: the prompt rule, the single `/repo` mount, and the commit/push prohibition
- [x] 4. `README.md` + `agent-wiki/2026-10-21-bot-implement-in-place.md` record the contract and the measured mount behaviour
- [x] 5. Verified: `make test-unit` green, `make check-docs`, `make lint`, `make check-wiring`, `make openspec-validate NAME=bot-implement-in-place` green, plus the container proof that a write outside `/repo` never reaches the host and one inside does
