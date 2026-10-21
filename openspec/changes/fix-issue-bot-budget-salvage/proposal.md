# fix-issue-bot-budget-salvage

## Why

`issue-bot.yml`'s `implement` job allows 120 minutes and every minute of the implement step is
invisible until the run finishes or is killed. Measured in run `39609465354`: 61 minutes inside
"Implement the issue", with detection, commit, push and the PR all *after* it — so a run that hits
the ceiling is `CANCELLED`, and the agent's work dies with the runner: no branch, no PR, and a
failure that reads like an infrastructure hiccup.

Issue: [#476](https://github.com/asimov-agent/llgenie/issues/476).

## What Changes

- `.github/workflows/issue-bot.yml`: the implement step gets its **own** `timeout-minutes: 90`
  (below the job's 120), so it fails by name while 30 minutes remain.
- The change detection and the commit+push steps run with `always()`, so whatever the agent wrote
  is salvaged into the branch and (with `pr-body.md`, #429) a PR, even when the leg times out or
  fails.
- A step names the outcome: `Implementation budget: <outcome> after the leg's 90-minute budget …
  tree=… branch=… pushed=…`, so the log reads as a budget, not a mystery.
- Tests in `make test-unit`: the step budget exists and is smaller than the job's; detection and
  push are `always()`; the budget failure is named with what survived.

## Impact

- Affected specs: `issue-bot` (modified).
- Affected code: `.github/workflows/issue-bot.yml`, `tests/test_bot_time_budget.py`, README,
  `agent-wiki/`.

## Not covered

- A checkpoint commit *inside* the leg (before the long gate work) is the alternative shape the
  issue names; this change takes the budget-alarm shape plus `always()` salvage.
