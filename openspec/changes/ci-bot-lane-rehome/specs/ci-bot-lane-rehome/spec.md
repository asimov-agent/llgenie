# ci-bot-lane-rehome

## ADDED Requirements

### Requirement: a deactivated bot lane is dispatch/event-only or retired, never a scheduled lane with no driver

The six lanes #2701 deactivated (issue-bot, issue-dedupe, issue-refiner, architecture-bot,
registry-sync-review, search-smoke) SHALL keep a workflow whose `on.schedule:` is gone and whose
header states who triggers it now — a human `workflow_dispatch`, a GitHub `issues: labeled` event,
or the interactive host agent. The one lane whose landing function is already covered elsewhere
(rebase-bot, by AGENTS.md agent self-rebase + the allow-listed `engine-bump-rebase.yml`) SHALL be
retired: its workflow, its scripts, its `make` targets, its claim bot name, its skill, its
roster/exemption entries and its tests are removed so no orphaned wiring or dead file implies a
live lane. (`make lane-preflight` still resolves the workflow list; issue #2703)

#### Scenario: a deactivated lane stays usable on manual dispatch

Given the in-scope workflow files with their `schedule:` blocks removed after #2701;

When a reviewer reads any of the six kept lane headers;

Then it names who triggers the lane now (workflow_dispatch / issues event / host agent) and lists no
`on.schedule:` block.

- **Test:** `tests/test_workflows_valid.py::test_every_migrated_agent_leg_calls_the_composite_action`
  (kept lane headers resolve) and per-lane `grep` in `make lane-preflight`.

#### Scenario: rebase-bot is fully retired

Given the repository tree after this change;

When `make lane-preflight` and `git grep` run over the workflows, `scripts/`, `Makefile`,
`.hermes/skills/`, `bots/pause.toml` and the tests;

Then no `rebase-bot` workflow, `rebase_bot*.py/.sh`, `rebase-bot` make target or `rebase-bot` claim
bot name remains; `scripts/bot_claims.py` still supports the `rebase` work kind for the live
`engine-bump-rebase` lane; and the `.hermes/skills/rebase-conflict/` skill survives as a HOST skill
(the inner staging half `llgenie-pr-rebase` names, listed in `HOST_SKILLS`).

- **Test:** `tests/test_rebase_bot_retired.py` (dead-surface assertions)
