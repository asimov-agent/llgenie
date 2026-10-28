# Agent skills for the bots

One Hermes **project skill** per agent leg, in the layout Hermes itself discovers
(`.hermes/skills/<name>/SKILL.md`), preloaded by that leg with `hermes -s <name>`. They are the
contract each bot runs under: `Inputs` says what the host prepared, `Output` says the one file the
leg may write, `Rules` says what it must not do.

## Two trees, two kinds of agent — do not confuse them

| tree | whose behaviour | what it is |
|---|---|---|
| `.hermes/skills/` | the **CI legs** — the bots a workflow runs in the agent image | a `hermes -s <name>` contract for one leg; gated by `make check-agent-skills` (issue #577) |
| `agents/<profile>/` | the **host agents** — `llgenie-planner`, `llgenie-issse-implementer`, the Hermes profiles on the owner's machine | that profile's `SOUL.md` plus its `skills/`; gated by `make check-agent-profiles` and synced into the profile with `make sync-agent-profile PROFILE=<p>` (issue #791) |

A skill for a CI leg belongs here and is preloaded by a `Makefile` recipe. A skill a **host agent**
loads (or that profile's `SOUL.md`) belongs under `agents/<profile>/`: it is copied into
`~/.hermes/profiles/<profile>/` by the sync target, never by hand, and a change to it is an issue
plus a PR like any other. Nothing in this directory is copied into a profile, and nothing under
`agents/` is preloaded by a leg.

The repo's `skills/engines/` is a third, different thing: those describe inference servers and are
read by `scripts/engine_skills.py` → `make generate-engine-params`, never by an agent.

| skill | leg | what it decides |
|---|---|---|
| `bot-unattended` | every leg | the shared unattended contract (never ask, never wait) |
| `issue-triage` | `make issue-bot-triage` | `implement` / `refine` / `close` → `triage.md` |
| `issue-refiner` | `make issue-refiner` | restate the issue or say it is clear → `refine.md` |
| `issue-dedup` | `make issue-dedup` | duplicate or distinct → `dedup.md` |
| `issue-implement` | `make implement-issue` | the change + `pr-body.md` |
| `architecture-doc` | `make architecture-bot-doc` | rewrite `docs/ARCHITECTURE.md` |
| `agent-fetch` | `make agent-fetch` | one masked URL fetch → `$OUT` |
| `registry-sync-review` | `make registry-sync-review` | the green store's VRAM→model→server answer → `registry-review.md` |
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
