# bot-skill-contracts — proposal

Issue: [#577](https://github.com/asimov-agent/llgenie/issues/577)

## Why

Every bot leg of this repository carried its whole contract as one inline string in the `Makefile`
(or a script's heredoc), and every one of them opened with the same two moves: "Load AGENTS.md for
rules" plus a ~500-character `UNATTENDED: …` paragraph repeated verbatim. Measured on `main`
(`527a958`): `rebase-bot-agent` 313 chars, `_issue-refiner` 1183, `_issue-dedup` 1005,
`_issue-bot-triage` 1014, `_agent-fetch` 1087, `_architecture-bot-doc` 1230, `_implement-issue`
1629 — plus `scripts/fix_bot_rules.md` (2255 bytes) concatenated into the fix loop's prompt and the
rebase prompt assembled in `scripts/rebase_bot.sh`.

Three consequences, all measured:

1. **The bot's contract was not a file an agent can load — it was a string in a make recipe.**
   Changing what the triage bot may write meant editing the `Makefile`, in a 1000+ character line,
   next to unrelated targets.
2. **The unattended paragraph was duplicated seven times**, so a wording fix had to be applied
   seven times and two legs had already diverged.
3. **Every leg paid for the whole rulebook.** `AGENTS.md` is 1173 lines of repo-wide durable rules;
   `Load AGENTS.md for rules` made each run ingest all of it to learn what *its* bot may do.

Hermes already has the mechanism: project skills under `<repo>/.hermes/skills/**/SKILL.md`,
preloaded by name with `hermes -s <name>`.

## What Changes

- **`.hermes/skills/<bot>/SKILL.md`** — one project skill per leg: `issue-triage`, `issue-refiner`,
  `issue-dedup`, `issue-implement`, `architecture-doc`, `agent-fetch`, `rebase-conflict`,
  `pr-fix`, plus `bot-unattended`, which carries the shared unattended contract once. Each carries
  `## Inputs`, `## Output`, `## Rules`, and its frontmatter `name:` equals its directory name.
- **The Makefile legs** preload their skill with `-s <bot>,bot-unattended` and reduce the inline
  prompt to a pointer plus that run's parameters. The rebase prompt (`scripts/rebase_bot.sh`) and
  the fix loop (`scripts/fix_loop.sh`) use the same mechanism; `scripts/fix_bot_rules.md` is
  retired into `pr-fix`.
- **`scripts/check_agent_skills.py` + `make check-agent-skills` / `make agent-skills-report`,
  run by `ci-unit`** — a leg with no `-s`, a missing / misnamed / incomplete skill, a prompt over
  the 400-char pointer budget, a duplicated shared contract, a returning rules file, or the rule's
  removal reds the gate.
- **`scripts/install_hermes_ci.sh`** sets `skills.trusted_project_dirs` to `/repo` and proves it
  landed: Hermes discovers a checkout's project skills only under a trusted root.
- **`tests/test_agent_skills.py`** proves each failure shape red; `tests/test_agents_unattended.py`
  and `tests/test_fix_loop.py` follow the contract to its new home.
- **README + `docs/AGENT-SKILLS.md` + `agent-wiki/`** document the layout and the gate.

## Not covered

- Rewriting `AGENTS.md` itself (splitting its rules into repo-wide vs bot-specific). This change
  adds the seam and the pointer.
- Hermetic *resolution* proof of `-s` inside the agent image (a live Hermes + model call). The
  image's config is asserted instead.
- **The `AGENTS.md` section itself**: Hermes refuses an unattended write to a protected
  agent-instruction file, so this run records the durable rule in `docs/AGENT-SKILLS.md` and the
  gate accepts either home. A human applies the same section to `AGENTS.md`.
