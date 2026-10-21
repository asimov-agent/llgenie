# fix-rebase-bot-actor-abort

## Why

The drain loop from #463 re-runs `make rebase-bot-sweep` after every rebase, and `make` must parse
`Makefile` before running any target. When a rebase stops on a conflict and the agent cannot resolve
it, `scripts/rebase_bot.sh` exited with the rebase **still stopped**: a conflict in `Makefile` (the
#446 case) then left the tree unparseable, and the loop's next decision died with
`Makefile:N: *** missing separator` — the #460 failure mode one level up. The fix commit that added
the abort landed after #463's squash merge, so `main` does not carry it
(`git show origin/main:scripts/rebase_bot.sh | grep -c abort_rebase` → `0`).

Issue: [#464](https://github.com/asimov-agent/llgenie/issues/464).

## What Changes

- `scripts/rebase_bot.sh`: `abort_rebase()` runs `git rebase --abort` (a no-op when nothing is in
  progress) on every failure path — agent failed, `rebase --continue` failed, conflict markers
  remain — so no `rebase-merge`/`rebase-apply` state survives a failed attempt.
- The failing-agent test asserts the tree is left with no stopped rebase.
- README states the rule.

## Impact

- Affected specs: `rebase-bot-sweep` (modified — failure paths leave a clean tree).
- Affected code: `scripts/rebase_bot.sh`, `tests/test_rebase_bot_sweep.py`, README, `agent-wiki/`.

## Not covered

- The loop and `rebase-bot-abort` target themselves are already on `main` (#463); this change only
  makes the actor leave a clean tree when it gives up.
