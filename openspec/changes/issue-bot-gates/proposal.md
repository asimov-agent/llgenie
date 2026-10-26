# issue-bot-gates — proposal

Issue: [#475](https://github.com/asimov-agent/llgenie/issues/475)

## Why

The issue-bot decides from the tree (`make issue-bot-changed`, #428) and refuses a PR body that says
nothing (`pr-body.md`, #429), but it still **opens the PR before anything checks the change against
the repository's own gates**. CI then discovers the bookkeeping reds, and a human (or the hourly
`fix-bot`) pays a round trip for them.

Measured in the run that implemented #407 and the six PRs opened from it (#443–#448): every one
carried the change correctly and passed the functional gates (`unit`, `lint`, `install`,
`cpu-health`, `top-tier`); the reds were bookkeeping only — `check_openspec_tasks` on an unticked
`- [ ]` in `tasks.md` (`ci-openspec`), a stale README target list, a wiring count. Each is
detectable in **seconds** by a host-side target, and each cost a full CI round trip plus a `fix-bot`
dispatch (up to an hour).

The bot's agent already runs the slow gates while it writes the change, so the marginal cost of the
fast ones is small. `trending-local-llms` answers this with a repair loop *after* the PR opens; that
shape is deliberately not imported here — `fix-bot` and `rebase-bot` already own PR repair, and a
second loop would be a second implementation of the same stage (AGENTS.md).

## What Changes

- **`make issue-bot-gates`** runs the fast repository gates in order and fails on the first,
  printing each gate and naming the failing one: `lint`, `check-workflows`, `check-wiring`,
  `check-docs`, `check-pr-hygiene`, `openspec-tasks-check`. It never runs `test-unit` (the agent
  already did, and it takes 11–20 minutes).
- **The list lives in ONE place**, `scripts/issue_bot_gates.py`: `FAST_GATES` (what the target
  runs) and `DEFERRED` (every other gate `ci-unit` runs, with the reason it is not re-checked
  before the push). `make issue-bot-gates` and `make issue-bot-gates-check` both go through that
  file, so there is no second roster to rot.
- **The issue-bot runs it between `Detect what the implementation changed` and
  `Commit + push the feature branch`** (`.github/workflows/issue-bot.yml`), conditioned on
  `verdict == 'implement'` and `changed == 'true'`, after a `make test-image` step — `lint` runs in
  `llgenie/test` exactly as `ci-lint` does, and a fresh runner has no such tag: a red gate fails the
  job loudly *before* the branch is pushed, naming the gate and the file, so nothing red reaches a
  reviewer and no `fix-bot` cycle is spent.
- **`make issue-bot-gates-check`** (and `tests/test_issue_bot_gates.py` under `make test-unit`)
  locks the wiring: a `ci-unit` gate classified neither fast nor deferred is a finding, a stale or
  contradictory classification is a finding, a fast gate that is not a `.PHONY` target or that no
  `ci-*` job reaches is a finding, a `issue-bot-gates` target that stopped running the runner is a
  finding, and so is a workflow step that is missing, duplicated, unconditional on a change, or
  not strictly between the detection and the push.
- **`ci-unit`** runs both targets, so the pipeline executes the same gate the bot does.

## Not covered

- The implement job's 120-minute ceiling and the absence of any budget evidence inside the run are
  [#476](https://github.com/asimov-agent/llgenie/issues/476).
- The post-PR repair loop `trending-local-llms` runs is deliberately **not** imported: `fix-bot`
  and `rebase-bot` own that stage here (one implementation per stage).
- Re-checking `check-agent-model`, `check-agent-skills`, `check-secret-output` and
  `check-dispatch-forms` before the push: they are fast, but #475 names a fixed six-gate list and
  widening it is a follow-up, not this change (`DEFERRED` records the decision).
