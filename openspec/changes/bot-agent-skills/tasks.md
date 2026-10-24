# Tasks

- [x] 1. `openspec/changes/bot-agent-skills` — proposal + `specs/bot-agent-skills/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before any code
- [x] 2. `.hermes/skills/` — one skill per leg (`bot-unattended`, `issue-triage`, `issue-refiner`, `issue-dedup`, `issue-implement`, `architecture-doc`, `agent-fetch`, `rebase-conflict`, `pr-fix`) with `## Inputs` / `## Output` / `## Rules`, and a `README.md` index
- [x] 3. Makefile — every leg preloads its skill with `-s` and keeps only a pointer prompt (88–179 chars, measured by `make agent-skills-report`)
- [x] 4. `scripts/fix_bot_rules.md` deleted; `scripts/fix_loop.sh` preloads `pr-fix,bot-unattended` and its prompt carries the run, not the rules
- [x] 5. `scripts/rebase_bot.sh` — the conflict prompt keeps the facts and points at `rebase-conflict`; the rules live in the skill
- [x] 6. `scripts/hermes_skills_register.py` — writes `skills.external_dirs` as a real YAML list, idempotent, `--check`, exit 2 on an unreadable config; called by `scripts/install_hermes_ci.sh` for `/repo/.hermes/skills` with a read-back; COPYed into the agent image and added to its hash inputs
- [x] 7. `scripts/check_agent_skills.py` + `make check-agent-skills` (in `ci-unit`, `.PHONY`, `##` help) and `make agent-skills-report`
- [x] 8. `tests/test_agent_skills.py` — every failure shape red against fixture trees, plus the real registration script and the wiring assertions
- [x] 9. `tests/test_agent_skills_live.py` + `make test-agent-skills-live` (run by `test-agents-read`, recorded in `tests/fixtures/unit-suite.json`) — Hermes's own preload path loads each leg's skills, and an unregistered home loads nothing
- [x] 10. `tests/test_agents_unattended.py` and `tests/test_fix_loop.py` — updated for the skill seam (the contract moved, the rule did not weaken)
- [x] 11. `AGENTS.md` — the rule that a bot's behaviour lives in its project skill, and how the image registers the directory
- [x] 12. `README.md` — the skill layout, the four targets, and why the registration is a written YAML list
- [x] 13. `agent-wiki/2026-10-24-bot-agent-skills.md` — the work record, referencing issue #577
- [x] 14. Verified: `make check-agent-skills`, `make test-unit` (tests/test_agent_skills.py tests/test_agents_unattended.py tests/test_fix_loop.py` (41 passed), `make test-agent-skills-live` (3 passed), `make lint`, `make check-wiring`, `make check-docs`, `make openspec-validate NAME=bot-agent-skills`
