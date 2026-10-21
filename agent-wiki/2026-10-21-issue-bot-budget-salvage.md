# 2026-10-21 — the issue-bot's implement leg has a budget and salvages its work (issue #476)

## What was wrong

Run `39609465354` spent 61 minutes inside "Implement the issue" — with detection, commit, push and
the PR all after it. A run that hits the job's 120-minute ceiling ends `CANCELLED`, the agent's
work dies with the runner, and no branch or PR exists.

## What changed

- `.github/workflows/issue-bot.yml`: the implement step declares `timeout-minutes: 90` (job 120);
  the change detection and the commit+push steps run with `always()`, so partial work is salvaged
  into the branch and (with `pr-body.md`) a PR.
- A step names the outcome: `Implementation budget: <outcome> after the leg's 90-minute budget …
  tree=… branch=… pushed=…`.
- `tests/test_bot_time_budget.py`: three tests pin the budget, the salvage conditions and the named
  failure.

## Verified

- `pytest tests/test_bot_time_budget.py` 8 passed; `make check-workflows` OK.
- Full unit suite recorded in the PR.

## Status

Issue #476; PR #486 from `feat/issue-bot-budget-salvage` against `asimov-agent/llgenie:main`. Waiting
for review — the agent never merges.
