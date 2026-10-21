# fix-rebase-bot-stale-again

## Why

The drain loop is live on `main`, but a dispatch (run 39590567679) rebased nothing:

```
[rebase-bot] pass-over: #447 was already rebased today
[rebase-bot] pass-over: #448 was already rebased today
stop: the sweep answered 'none' after 0 rebase(s)
```

#447 and #448 were `CONFLICTING`/`DIRTY` at that moment — they were rebased earlier in the day and
`main` moved afterwards. `rebased_today()` was consulted **before** the merge state, so a PR that
needed another rebase was skipped until the UTC date rolled over. The marker exists to stop a
rebase loop, not to block real work: after a successful rebase the PR reads `CLEAN`, so the sweep
cannot pick it again unless the tree moved.

Issue: [#467](https://github.com/asimov-agent/llgenie/issues/467).

## What Changes

- `scripts/rebase_bot_sweep.py`: the "already rebased today" early pass-over is gone; the markers
  keep bounding the daily cap only. A new `--skip` (sweep kwarg `skip`) passes over the PRs **this
  run** already rebased, so one run cannot loop on the same PR.
- `.github/workflows/rebase-bot.yml`: the drain loop accumulates the PR numbers it rebased
  (`skip="7,8"`) and passes `SKIP=` to each `make rebase-bot-sweep`.
- `Makefile`: `rebase-bot-sweep` forwards `SKIP=` as `--skip`.
- Tests: a re-dirtied PR with today's marker is picked; `--skip` keeps a run from repeating a PR;
  the loop forwards the list; the marker still counts toward the cap.

## Impact

- Affected specs: `rebase-bot-sweep` (modified — eligibility vs the daily record).
- Affected code: `scripts/rebase_bot_sweep.py`, `.github/workflows/rebase-bot.yml`, `Makefile`,
  `tests/test_rebase_bot_sweep.py`, README, `agent-wiki/`.
- Unchanged: the daily cap value, the cron, the merge-state logic and the abort behaviour.

## Not covered

- A PR rebased twice within the same day now consumes two slots of the daily cap; the cap value is
  not raised here.
