# Bot legs run on project skills (issue #577)

Every bot leg of this repository used to carry its whole contract as one inline string in the
`Makefile` (or a script's heredoc): the triage rules, the refiner's review instruction, the
implementer's hard rules, and the ~500-character `UNATTENDED: …` paragraph repeated verbatim in
each of them. Changing what a bot may write meant editing a 1000+ character make recipe next to
unrelated targets, the unattended paragraph had to be fixed in seven places (two had already
drifted), and every run ingested the whole rulebook to learn its own fraction.

This document records the replacement: one project skill per leg, preloaded by name.

## Every bot leg's contract is a project skill

A bot leg's contract is a markdown file under `.hermes/skills/<name>/SKILL.md`, preloaded by name
with `hermes -s <bot>,bot-unattended`. It is never an inline string in a make recipe or a script
heredoc.

- **One skill per leg**: `issue-triage`, `issue-refiner`, `issue-dedup`, `issue-implement`,
  `architecture-doc`, `agent-fetch`, `rebase-conflict`, `pr-fix`. **One shared skill**,
  `bot-unattended`, carries the unattended contract ONCE — never ask, a question fails the run,
  and the path a genuinely open decision takes.
- **Each skill carries `## Inputs`, `## Output` and `## Rules`**, and its frontmatter `name:`
  equals its directory name. That file is what an agent loads and what a reviewer reads;
  changing what a bot may write means editing that file, not a 1000-character recipe.
- **The leg's inline prompt is a pointer plus that run's parameters**, under the
  `MAX_PROMPT_CHARS` budget `scripts/check_agent_skills.py` enforces (400 chars). A rulebook
  creeping back into the recipe is a defect, and so is a second rules file
  (`scripts/fix_bot_rules.md` was retired into `pr-fix`).
- **The agent image trusts `/repo` for project skills** (`scripts/install_hermes_ci.sh` sets
  `skills.trusted_project_dirs`): Hermes only discovers a checkout's project skills when its root
  is trusted, and a runtime without that config would load no skill at all.
- **`make check-agent-skills`** (`scripts/check_agent_skills.py check`, run by `ci-unit`) is the
  gate: a leg with no `-s`, a missing / misnamed / incomplete skill, a prompt over budget, a
  duplicated shared contract, a returning rules file, or this rule's removal. `make
  agent-skills-report` prints every leg, its prompt size and each skill's sections. Tests:
  `tests/test_agent_skills.py` in `make test-unit`.

## Why the rule lives here as well as in `AGENTS.md`

`AGENTS.md` is the repository rulebook and the rule belongs there. It is also a **protected
agent-instruction file**: Hermes refuses an unattended write to it and requires a human to approve
one, by design. An implementer running with no user attached therefore cannot add the section, so
this document carries the same rule and `make check-agent-skills` accepts either home. When a
human applies the section to `AGENTS.md`, this pointer stays valid and the gate keeps accepting
both.
