# 2026-10-24 — every bot leg loads its contract from a Hermes project skill

Issue: [#577](https://github.com/asimov-agent/llgenie/issues/577)
OpenSpec: `openspec/changes/bot-agent-skills`
PR: (opened from `feat/bot-agent-skills-577`)

## What changed

The bots' contracts were inline strings in the `Makefile`: 1005–1629 characters per leg, the same
`UNATTENDED: …` paragraph seven times, and `Load AGENTS.md for rules` at the start of each. They are
now **Hermes project skills** in `.hermes/skills/<name>/SKILL.md`, preloaded with `hermes -s <name>`,
and each leg's prompt is a pointer plus that run's parameters (88–179 characters, printed by
`make agent-skills-report`).

- Nine skills: `bot-unattended` (the shared contract, once), `issue-triage`, `issue-refiner`,
  `issue-dedup`, `issue-implement`, `architecture-doc`, `agent-fetch`, `rebase-conflict`, `pr-fix`.
  Each has `## Inputs`, `## Output` (the ONE file the leg may write) and `## Rules`.
- `scripts/fix_bot_rules.md` is gone: the fix bot preloads `pr-fix` and its prompt carries the failing
  check, not the rules. The rebase conflict prompt likewise keeps the facts only.
- The agent image registers `/repo/.hermes/skills` in `skills.external_dirs` at build time
  (`scripts/hermes_skills_register.py` from `scripts/install_hermes_ci.sh`) and reads it back.

## Decisions worth keeping

- **`skills.external_dirs`, not project discovery.** `trusted_project_dirs` needs a much newer Hermes
  than the repo's pinned `hermes-agent==0.19.0`, and an older CLI would preload nothing — silently.
  `external_dirs` exists on both and needs no cwd.
- **The registration is written as a YAML list, not by `hermes config set`.** Measured: 0.19.0 stores
  `'["/repo/.hermes/skills"]'` as an opaque string (which resolves to no directory), the current CLI
  refuses a string ("must be a list"). A real list is read correctly by both.
- **The load is proven, not assumed.** `tests/test_agent_skills_live.py` feeds each leg's `-s` list to
  `agent.skill_commands.build_preloaded_skills_prompt` — the function `hermes -z … -s` calls before the
  model's first turn — against a home registered by the image's own script: every name resolves and
  each skill's `description` is in the rendered prompt. The negative case (unregistered home) resolves
  nothing.
- The hermetic gate also refuses a rulebook creeping back (400-character budget), an inlined
  unattended contract, a skill nothing preloads, and a returned `scripts/fix_bot_rules.md`.

## Verified

- `make check-agent-skills` — 8 legs, 9 skills, 0 findings.
- `tests/test_agent_skills.py` + `tests/test_agents_unattended.py` + `tests/test_fix_loop.py` — 41
  passed in the test image, all failure shapes driven through the real guard and real scripts.
- `make test-agent-skills-live` — 3 passed against the pinned `hermes-agent` (the skills load).
- `make lint`, `make check-wiring`, `make check-docs`, `make openspec-validate NAME=bot-agent-skills`.

## Still open

The `agents-read` venv pins `hermes-agent==0.19.0` (the newest on PyPI). It loads skills from
`external_dirs`, which is what this change relies on; nothing here needs a newer CLI.
