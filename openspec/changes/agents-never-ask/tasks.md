# Tasks — agents-never-ask (issue #543)

- [x] 1. OpenSpec change: `proposal.md`, `specs/agents-never-ask/spec.md`, this checklist
- [x] 2. The UNATTENDED rule on all five `hermes -z` prompts (`_issue-bot-triage`, `_implement-issue`, `_issue-refiner`, `_architecture-bot-doc`, `_agent-fetch`)
- [x] 3. `scripts/fix_bot_rules.md`: a "You are unattended" section (clarify detaches with exit 3)
- [x] 4. `issue-bot.yml`: the `rc == 3` branch names "the agent asked for input", before the generic message
- [x] 5. `tests/test_agents_unattended.py`: prompts + rules + workflow
- [x] 6. `README.md` + `agent-wiki/2026-10-23-agents-never-ask.md`
- [x] 7. Verified: `pytest tests/test_agents_unattended.py` → 3 passed; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=agents-never-ask`, `make openspec-tasks-check`; `make test-unit` in the PR checks
- [x] 8. PR opened against `asimov-agent/llgenie:main` closing #543
