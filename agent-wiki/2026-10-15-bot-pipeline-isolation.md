# Each bot on its own pipeline: a unique cron slot, its own concurrency group

Related: issue #275 (this change), resolving #271 and #272. Complements #261/#263
(the bots also claim issues in comments — that is the *work* coordination; this is the
*schedule and run* coordination).

## The problem

The bots were already separate workflow *files*, but they still collided:

- **Two cron pairs shared a minute.** `engine-bump-rebase` (daily 05:17) vs `registry-sync`
  (Mon 05:17) — #271; `engine-bump` (Mon 06:23) vs `issue-bot` (daily 06:23) — #272. Both pairs
  run `make` on a fresh checkout of `main` and push branches / open PRs, so a shared slot meant
  two bots doing independent writes beside each other with nothing coordinating them.
- **Three bot workflows had no `concurrency:` group at all** (`engine-bump`,
  `engine-bump-rebase`, `registry-sync`), so a manual `workflow_dispatch` launched during a
  scheduled run of the same bot ran a second instance in parallel.

## The rule

Every bot owns a cron **minute no other bot uses on any day**, and its own `concurrency:` group
named after the bot with `cancel-in-progress: false`.

| Bot | Cron | Minute today |
|---|---|---|
| `issue-bot` | `23 6 * * *` | daily 06:23 |
| `fix-bot` | `17 * * * *` | hourly at :17 |
| `queued-alarm` | `7,37 * * * *` | :07 and :37 |
| `engine-bump-rebase` | `41 5 * * *` | daily 05:41 |
| `registry-sync` | `19 5 * * 1` | Monday 05:19 |
| `engine-bump` | `53 6 * * 1` | Monday 06:53 |

The uniqueness is a `(minute, weekday)` property, not an hour: a daily/weekly bot on minute 17
would still collide with the hourly `fix-bot` every day, so the hourly bots' minutes
(17, 7, 37) are reserved on every weekday.

## Where it lives

The schedule is the two workflow files per bot; the guard is
`tests/test_bot_pipeline_isolation.py`, in `make test-unit`. It expands each scheduled cron into
the `(minute, weekday)` slots it owns and fails when two bots share a slot, when a bot reuses a
reserved hourly minute, or when a bot declares no concurrency group. A future bot that lands on
a used slot therefore goes red at `ci-unit` instead of silently racing.
