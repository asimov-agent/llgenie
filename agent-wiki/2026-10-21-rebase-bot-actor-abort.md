# 2026-10-21 — a failed rebase leaves a clean tree for the next decision (issue #464)

## What was wrong

The drain loop (#463) re-runs `make rebase-bot-sweep` after every rebase, and `make` must parse
`Makefile` before any target. On a conflict the agent could not resolve, `scripts/rebase_bot.sh`
exited with the rebase still stopped, so a conflict in `Makefile` left the tree unparseable and the
next decision died with `Makefile:N: *** missing separator` — the #460 failure mode one level up.
The abort had been written as part of #463 but landed after its squash merge, so `main` did not
carry it (`git show origin/main:scripts/rebase_bot.sh | grep -c abort_rebase` → `0`).

## What changed

- `scripts/rebase_bot.sh`: `abort_rebase()` runs `git rebase --abort` (no-op when nothing is in
  progress) on every failure path — agent failed, `rebase --continue` failed, conflict markers
  remain.
- `tests/test_rebase_bot_sweep.py`: the failing-agent test asserts no `rebase-merge`/`rebase-apply`
  state remains.
- README states the rule; OpenSpec change `fix-rebase-bot-actor-abort`.

## Verified

- `pytest tests/test_rebase_bot_sweep.py tests/test_bot_decision_loudness.py` 37 passed.
- Full unit suite and structural gates recorded in the PR.

## Status

Issue #464; PR #465 from `feat/rebase-bot-actor-abort` against `asimov-agent/llgenie:main`. Waiting for
review — the agent never merges.
