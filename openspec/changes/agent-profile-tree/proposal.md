# agent-profile-tree — proposal

Issue: [#791](https://github.com/asimov-agent/llgenie/issues/791)

## Why

The bots' contracts live in `.hermes/skills/`, are preloaded with `hermes -s <name>` and are gated by
`make check-agent-skills` (issue #577). The two **host** agents are the opposite: `llgenie-planner`
(the orchestrator) and `llgenie-issse-implementer` (the implementer) keep `SOUL.md` plus `skills/`
in `~/.hermes/profiles/<profile>/`, outside version control. Measured on `main@17cdcf3`:
`git log --all --oneline -- '*SOUL*'` returns nothing and `agents/` does not exist.

So an instruction that changes a credential-holding agent's behaviour was the one change in this
repository nobody could diff or review. A phantom claim (#769) or an unapproved merge (PR #776,
approved and merged by `asimov-agent` five seconds apart) cannot be traced to the instruction that
permitted it, a profile reinstall or a new machine silently loses the behaviour, and the two halves
of the fleet drift — the bot legs' rules are reviewed and gated, the host agents' are not, though they
hold the write credentials.

## What Changes

- **A home in the tree**: `agents/manifest.json`, `agents/llgenie-planner/SOUL.md`,
  `agents/llgenie-planner/skills/llgenie-bot-orchestration/` (the skill plus the `references/` file it
  names) and `agents/llgenie-issse-implementer/SOUL.md`, one directory per profile, mirroring the
  layout Hermes loads.
- **`make sync-agent-profile PROFILE=<p> [CHECK=1]`** (`scripts/agent_profile_sync.py`, stdlib only):
  copy `agents/<p>/` into the profile's Hermes home — `--dest`, else `$HERMES_PROFILE_HOME`, else
  `~/.hermes/profiles/<p>/` — then read every file back; `CHECK=1` compares instead and names the
  first differing path. Exit 2 on a profile the manifest does not list. It writes only the files the
  tree carries, so a profile's own skills, memory, `state.db` and `.env` are untouched, and there is
  no delete path.
- **`make check-agent-profiles`** (`scripts/check_agent_profiles.py`), wired into `ci-unit` beside
  `check-agent-skills`: a listed profile with no directory, a directory the manifest does not list, a
  profile with no `SOUL.md`, a skill whose frontmatter `name` disagrees with its directory (or has no
  frontmatter, or an empty `description:`), a skill naming a `references/<file>.md` that is not in the
  tree, a secret-shaped value in any committed file, a `SOUL.md` that dropped a standing rule its
  manifest entry declares (the orchestrator: `never-implement`, `never-merge`), a manifest that
  declares `never-merge` for no profile, and any profile data (`state.db`, `sessions/`, `memories/`,
  `logs/`, `.env`) in the tree. `make agent-profiles-report` prints what it reads.
- **`tests/test_agent_profiles.py`** (discovered by `make test-unit`): the committed tree, one
  rejection per gate rule above against fixture trees, and the real sync against a temporary
  `HERMES_PROFILE_HOME`.
- **The split is stated**: `.hermes/skills/README.md` names the two trees and which agent each one is
  for; `docs/BOTS.md` documents both behaviour and both targets.

## Not covered

- The CI legs' own contracts: already in-tree under `.hermes/skills/` (issue #577) — this change does
  not move or regate them.
- The profiles' memory, sessions and state databases: not behaviour, and the gate refuses them.

## Verification

`make check-agent-profiles`, `make check-agent-skills`, `make check-docs`, `make check-wiring` and
`make test-unit` all green; the host-only proof (`CHECK=1` against the owner's live profiles) is
recorded in `agent-wiki/2026-10-28-agent-profiles-tree.md`.
