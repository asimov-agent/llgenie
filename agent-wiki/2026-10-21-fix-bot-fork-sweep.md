# 2026-10-21 — the fix-bot can select the repository's own fork (issue #340)

## What was wrong

`scripts/fix_bot_sweep.py` required a PR whose head is in the BASE repository, and the workflow
pushed to `origin`. Every llgenie PR is opened from `andyholst:...` (AGENTS.md's PR rule), so the
hourly scheduled sweep passed over every real PR and repaired nothing — eight green no-op runs.
The sibling `rebase-bot-sweep` already solved it with `--own-fork`.

## What changed

- `scripts/fix_bot_sweep.py`: `--own-fork <owner>`; a PR is pushable when its head owner is the
  base repo owner OR that fork. Any other fork stays skipped.
- `Makefile`: `fix-bot-sweep` forwards `OWN_FORK=`.
- `.github/workflows/fix-bot.yml`: the sweep passes `OWN_FORK=andyholst`; the fix job records the
  PR's head repository, checks the base out on `main`, fetches the branch from its own remote
  (`fork`, with the PAT) and checks it out, and pushes with `--force-with-lease` to `REMOTE` —
  the PR's head remote, never `main`.

## Verified

- `pytest tests/test_fix_bot_sweep.py` 14 passed: the allowlisted fork PR is chosen and dispatched;
  a third-party fork is still skipped with its reason; the workflow fetches from the fork and
  pushes to `REMOTE`.
- Structural gates and the full unit suite are recorded in the PR.

## Status

Issue #340; PR #477 from `feat/fix-bot-fork-sweep` against `asimov-agent/llgenie:main`. Waiting for
review — the agent never merges.
