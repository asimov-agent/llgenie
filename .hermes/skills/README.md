# Agent skills for the bots

One Hermes **project skill** per agent leg, in the layout Hermes itself discovers
(`.hermes/skills/<name>/SKILL.md`), preloaded by that leg with `hermes -s <name>`. They are the
contract each bot runs under: `Inputs` says what the host prepared, `Output` says the one file the
leg may write, `Rules` says what it must not do.

The repo's `skills/engines/` is a different thing: those describe inference servers and are read by
`scripts/engine_skills.py` → `make generate-engine-params`, never by an agent.

| skill | leg | what it decides |
|---|---|---|
| `bot-unattended` | every leg | the shared unattended contract (never ask, never wait) |
| `issue-triage` | `make issue-bot-triage` | `implement` / `refine` / `close` → `triage.md` |
| `issue-refiner` | `make issue-refiner` | restate the issue or say it is clear → `refine.md` |
| `issue-dedup` | `make issue-dedup` | duplicate or distinct → `dedup.md` |
| `issue-implement` | `make implement-issue` | the change + `pr-body.md` |
| `architecture-doc` | `make architecture-bot-doc` | rewrite `docs/ARCHITECTURE.md` |
| `agent-fetch` | `make agent-fetch` | one masked URL fetch → `$OUT` |
| `rebase-conflict` | `make rebase-bot-agent` | resolve a stopped rebase |
| `pr-fix` | `make fix-loop-image` | repair a red PR check |

Rules for adding one:

- A leg's inline prompt in the `Makefile` is a **pointer plus its parameters** — the rules live in
  the skill. `make check-agent-skills` fails a leg whose prompt grows past the pointer budget, whose
  `-s` names a skill that does not exist, or whose skill's frontmatter `name` does not match its
  directory.
- Hermes reads skills from its own home and from `skills.external_dirs`: the agent image registers
  `/repo/.hermes/skills` there (`scripts/hermes_skills_register.py`, called by
  `scripts/install_hermes_ci.sh`) and reads the value back, so an unregistered checkout cannot
  quietly preload nothing.
- Never put a secret's value in a skill. Name the environment variable, as `agent-fetch` does.
