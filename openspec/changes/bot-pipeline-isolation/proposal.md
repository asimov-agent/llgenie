# Give each bot its own isolated pipeline (no two bots conflict)

## Why

The bots are in separate workflow *files* but still step on each other, in two measured ways:

1. **Shared cron slots.** `engine-bump-rebase.yml` fires `17 5 * * *` (daily 05:17 UTC) and
   `registry-sync.yml` fires `17 5 * * 1` (Mon 05:17 UTC) — on Mondays both run at the same
   minute (#271). `engine-bump.yml` fires `23 6 * * 1` (Mon 06:23 UTC) and `issue-bot.yml` fires
   `23 6 * * *` (daily 06:23 UTC) — on Mondays both run at the same minute (#272). Both
   colliding pairs run `make` on a fresh checkout of `main` and push branches / open PRs side
   by side with no coordination.
2. **Missing concurrency isolation.** `engine-bump.yml`, `engine-bump-rebase.yml` and
   `registry-sync.yml` declare no `concurrency:` group at all. A manual `workflow_dispatch` of
   any of them, launched while its scheduled run is still going, runs a second instance in
   parallel with no queueing.

The fix is to make the isolation structural: every bot gets a cron minute no other bot owns on
any day, and every bot workflow gets its own concurrency group.

## What changes

- Rewrite the six bot cron lines so no two bots share a `(minute, weekday)` slot:
  - `issue-bot`: `23 6 * * *` (keep, minute 23)
  - `fix-bot`: `17 * * * *` (keep, minute 17)
  - `queued-alarm`: `7,37 * * * *` (keep, minutes 7 & 37)
  - `engine-bump-rebase`: `17 5 * * *` → `41 5 * * *` (minute 41; was colliding with fix-bot's 17)
  - `engine-bump`: `23 6 * * 1` → `53 6 * * 1` (minute 53; was colliding with issue-bot's 23)
  - `registry-sync`: `17 5 * * 1` → `19 5 * * 1` (minute 19; was colliding with fix-bot / engine-bump-rebase)
- Give every bot workflow its own `concurrency:` group with `cancel-in-progress: false`:
  add one to `engine-bump`, `engine-bump-rebase` and `registry-sync` (the other four already
  have one and keep it).
- `tests/test_bot_pipeline_isolation.py` (wired into `make test-unit`) parses every scheduled
  `.github/workflows/*.yml`, expands each bot's cron into its owned `(minute, weekday)` pairs,
  and asserts no pair is owned by more than one bot — a future bot that lands on a used slot
  (including minute 17/7/37 used by the hourly bots) goes red at `ci-unit`.
- Update `README.md` (bot pipeline section) and add an `agent-wiki/` entry in the same commit.

## Impact

Scheduled bots no longer collide on the same minute, and a manual dispatch versus a scheduled
run of the same bot is serialised instead of overlapping. Cron behaviour is otherwise unchanged
(hour/minute of daily and weekly runs stays in the same time window).

Resolves #271 and #272; closes the per-bot concurrency gap. Out of scope (separate issues):
#270 (queued-alarm runs a script directly, not a make target), #269 (code-review bot), #273
(missing NOUS_PORTAL_API_TOKEN secret).
