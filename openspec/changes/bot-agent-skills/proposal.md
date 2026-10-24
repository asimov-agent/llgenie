# bot-agent-skills — proposal

Issue: [#577](https://github.com/asimov-agent/llgenie/issues/577)

## Why

Every bot leg carried its whole contract as one inline string in the `Makefile` (or a script's
heredoc), and every one started with the same two moves: `Load AGENTS.md for rules` and a
~500-character `UNATTENDED: …` paragraph repeated verbatim. Measured on `main` (`527a958`):

| leg | where | inline prompt |
|---|---|---|
| `rebase-bot-agent` | `Makefile` | 313 chars (the conflict prompt arrives on STDIN) |
| `_issue-refiner` | `Makefile` | 1183 chars |
| `_issue-dedup` | `Makefile` | 1005 chars |
| `_issue-bot-triage` | `Makefile` | 1014 chars |
| `_agent-fetch` | `Makefile` | 1087 chars |
| `_architecture-bot-doc` | `Makefile` | 1230 chars |
| `_implement-issue` | `Makefile` | 1629 chars |
| the fix bot | `scripts/fix_bot_rules.md` (2255 bytes) cat'ed into the prompt by `scripts/fix_loop.sh` | — |

Three consequences:

1. **A bot's contract is not a file an agent can load; it is a string in a make recipe.** Changing
   what the triage bot may write means editing a 1000+ character line next to unrelated targets, and
   nothing lists the bots' contracts together.
2. **The unattended paragraph is duplicated seven times**, and it already diverged: `_issue-dedup`
   said "choose DISTINCT", the refiner said "a refine with its REFINED/REASON".
3. **Every leg pays for the whole rulebook.** `AGENTS.md` is 1173 lines of repo-wide rules;
   `Load AGENTS.md for rules` makes each run ingest all of it to learn what *its* bot may do.

Hermes has the mechanism this should use — skills (`SKILL.md`, preloaded with `hermes -s <name>`).
The repo vendors engine skills in `skills/engines/` (read by `generate-engine-params`, never by an
agent) but had no agent-facing skill at all.

## What Changes

- **`.hermes/skills/<name>/SKILL.md`** — one skill per leg: `bot-unattended` (the shared contract,
  once), `issue-triage`, `issue-refiner`, `issue-dedup`, `issue-implement`, `architecture-doc`,
  `agent-fetch`, `rebase-conflict`, `pr-fix`. Each carries `## Inputs`, `## Output` (the ONE file the
  leg may write) and `## Rules`.
- **Every leg preloads its skill** with `-s <name>,bot-unattended`, and its inline prompt becomes a
  pointer plus that run's parameters (88–179 characters).
- **The fix bot's rules file moves into the `pr-fix` skill.** `scripts/fix_bot_rules.md` is deleted,
  and `scripts/fix_loop.sh` preloads the skill instead of concatenating a file into the prompt. The
  rebase bot's prompt keeps the conflict facts and points at `rebase-conflict`.
- **`scripts/hermes_skills_register.py`** registers the checkout's `.hermes/skills` in
  `skills.external_dirs` of the Hermes home, and `scripts/install_hermes_ci.sh` calls it at image
  build time (`/repo/.hermes/skills`, the path every leg runs in) and reads the value back. It writes
  a real YAML **list**: `hermes config set` takes a list on a newer CLI but stores a JSON literal as
  an opaque string on the pinned `hermes-agent==0.19.0`, which resolves to no directory at all.
- **`scripts/check_agent_skills.py` + `make check-agent-skills`** (in `ci-unit`) fail a leg with no
  `-s`, an unknown skill name, a frontmatter/directory mismatch, a skill missing a section, a prompt
  over the 400-character budget, an inlined unattended contract, a skill no leg preloads, a returned
  `scripts/fix_bot_rules.md`, or an `AGENTS.md` without the rule. `make agent-skills-report` prints
  what it reads.
- **`tests/test_agent_skills.py`** proves every failure shape red against fixture trees, and drives
  the real registration script.
- **`tests/test_agent_skills_live.py` + `make test-agent-skills-live`** prove Hermes actually LOADS
  each leg's skills: each `-s` list goes through `agent.skill_commands.build_preloaded_skills_prompt`
  (the function `hermes -z … -s` calls before the first turn) against a home registered by the image's
  own script, asserting every name resolved and each skill's content is in the prompt the model
  receives — plus the negative: an unregistered home resolves nothing.
- `AGENTS.md` states the rule; `README.md` documents the layout and the four targets; an
  `agent-wiki/` entry records the work.

## Benefit

- A bot's contract is a reviewable markdown file, changed in one place and loaded through Hermes
  instead of pasted into a recipe.
- The shared unattended contract exists once, so its divergence cannot recur.
- Each run loads its own bot's rules instead of the whole `AGENTS.md` plus a duplicated preamble.
- A leg that would run with no contract is a red gate, not a silent 90-minute run.
