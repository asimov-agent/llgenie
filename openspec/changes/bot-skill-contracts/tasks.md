# Tasks

- [x] 1. `.hermes/skills/` holds one skill per leg (`bot-unattended`, `issue-triage`, `issue-refiner`, `issue-dedup`, `issue-implement`, `architecture-doc`, `agent-fetch`, `rebase-conflict`, `pr-fix`), each with `## Inputs` / `## Output` / `## Rules` and `name` == directory
- [x] 2. Every `hermes -z` leg preloads its skill with `-s <bot>,bot-unattended`, and its inline prompt is a pointer plus the run's parameters (Makefile legs, `rebase-bot-agent`, the `pr-fix` loop)
- [x] 3. `scripts/fix_bot_rules.md` is retired into `pr-fix`; `scripts/fix_loop.sh` and `scripts/rebase_bot.sh` carry no second rules file
- [x] 4. `scripts/check_agent_skills.py` (`check` / `report`) + `make check-agent-skills` / `make agent-skills-report`, in `.PHONY` and in `ci-unit`
- [x] 5. `tests/test_agent_skills.py` proves each failure shape red (leg without `-s`, missing skill, name mismatch, missing section, prompt over budget, duplicated contract, second rules file, rule removed, no leg at all); `make test-unit` discovers it
- [x] 6. `tests/test_agents_unattended.py` and `tests/test_fix_loop.py` now read the contract from its skill, not from the retired rules file
- [x] 7. `scripts/install_hermes_ci.sh` sets `skills.trusted_project_dirs` to `/repo` and proves it landed; the agent Dockerfile runs it
- [x] 8. README documents the skill layout and the gate; `docs/AGENT-SKILLS.md` records the rule (AGENTS.md is a protected agent-instruction file, so the unattended run records it there and the gate accepts either); `agent-wiki/` records the change with issue #577
- [x] 9. Verification: `make check-agent-skills`, `make agent-skills-report`, `make check-wiring`, `make check-docs`, `make check-secret-output` exit 0 on the real tree, and the new/updated pytest files pass
