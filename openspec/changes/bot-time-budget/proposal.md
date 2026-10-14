# Give the bots the time their work actually needs

## Why

Both bots hand a long task to an agent and then re-run the repo's own gates, but the fix-bot's job
allowed 120 minutes while its own worst case is larger: `FIX_ROUNDS` (default 3) rounds of
`make ci-unit` (measured 11-20 minutes on a linux runner) plus an agent repair (10-30 minutes) is
up to 150 minutes. A job killed at the cap ends the run as CANCELLED, which reads as an
infrastructure hiccup instead of the loop's own "still failing after N attempts" verdict, and it
throws away the agent's work for that round.

Nothing else bounds a round: no step-level `timeout-minutes`, no `timeout` inside
`scripts/fix_loop.sh`, and no step or wall-clock cap on the Hermes call. The job budget *is* the
effective limit, so it has to fit the work.

## What changes

- The fix-bot's `fix` job allows **180 minutes** (under GitHub's 360-minute ceiling), with the
  arithmetic written in the workflow header where a maintainer reads it.
- `tests/test_bot_time_budget.py` pins the invariant against the loop's own default: a bot job
  that runs an agent must allow at least an hour, the fix job must fit `rounds x (check +
  repair)`, no step may cap below that, the decision-only guard/sweep jobs keep a tight budget,
  and `scripts/fix_loop.sh` must not hide a `timeout` of its own.

## Impact

More CI minutes are possible for a hard repair (up to 3 hours), which is the point: the bot is
either allowed to finish or it reports its own verdict. The decision-only jobs are unchanged.
