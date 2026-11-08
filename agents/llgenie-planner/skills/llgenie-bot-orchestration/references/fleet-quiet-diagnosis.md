# A quiet fleet: find the missing dispatch, not the lazy lane

When the owner asks "why is only one lane working?" / "why are the PRs still red?", the answer is almost
never a lazy lane. **Every host lane is turn-based: it runs one turn and exits.** Nothing persists between
turns, so a lane cannot be "quiet" on its own — it is quiet because nothing dispatched it. Diagnose the
dispatch mechanism before you diagnose any lane.

## Diagnostic order (cheapest first)

1. `hermes cron status` — is the scheduler alive, and does it list active jobs? Note whether it prints an
   OVERDUE warning; that warning is the answer more often than not.
2. `hermes cron list` (per profile) and read `cron/jobs.json` directly for the authoritative `enabled` flag —
   the CLI's "no active jobs" and a job entry with `enabled: false` are the same fact stated two ways.
3. Only then measure lanes (`state.db` mtime, start bookends, live `bot_mode_dm.py` process — see
   `host-lane-precedence-over-ci.md`).

If step 1 or 2 shows the jobs disabled or overdue, **every lane will be idle and every PR red** regardless of
what any lane does. Fix the mechanism, then re-measure the board.

## The overdue-`next_run` trap

A resumed job can come back with `next_run` set to a timestamp **hours or days in the past**, and the
scheduler will sit there with a live heartbeat and never fire it. Two field states make this invisible:

- `last_status: 'ok'` is written even for a job that has **never run** (`last_run: None`). Do not read `ok`
  as evidence of execution.
- `cron status` can print a healthy `Ticker heartbeat: Ns ago` in the same breath as
  `Next run … is OVERDUE — passed 4h 23m ago but the job has not fired (is the scheduler running?)`.

**Repair that works:** `hermes cron run <id>` — it recomputes `next_run` into the future *and* executes the
job once. `resume` alone does not recompute; it restores the stale deadline. Verify by re-reading `cron
status` and confirming `Next run` is in the future, not by trusting the resume output.

Compute how many slots were lost (`overdue ÷ interval`) before reporting — "26 ticks skipped silently" is
the sentence that makes the owner act, and it is a real number you can measure.

## Boundary: your crons are yours, a lane's crons are theirs

The planner's own recurring tick is the fleet's dispatch generator. **Other profiles' cron jobs are not yours
to enable, resume, pause or edit** — not even to "help the fleet move", and not even when they are the
obvious cause of a red PR. A lane's scheduler is that lane's configuration; touching it silently changes
another agent's behaviour, and the owner will (rightly) ask whether you only touched your own.

- Inspect any profile read-only: `hermes cron status -p <profile>`, read
  `~/.hermes/profiles/<profile>/cron/jobs.json`, `hermes cron runs <id> -p <profile>`.
- Change only `llgenie-planner`'s own jobs. If another lane's cron is disabled or broken, **report it** — or
  file it for that lane — do not flip it.
- If you already flipped one, revert it (`hermes cron pause <id> -p <profile>`) and say so plainly. Reverting
  is cheap; leaving it on is a silent change to someone else's agent.

## Before blaming a lane's cron, check its run history

`hermes cron runs <id> -p <profile>` distinguishes three very different states:

- **completed, long ago** → the job was turned off; nothing is broken, it is simply disabled.
- **failed with a traceback every tick** → the job is on but broken. Read the stderr; a script that shells
  out to a bare binary (e.g. `subprocess.run(["gh", …])`) can fail in the cron context's narrower `PATH` even
  though the same command works in an interactive shell. The fix belongs to that lane: absolute path, or
  `PATH` in the job's env — never "the tool is broken".
- **no runs at all** → it has never fired (the overdue trap above).

Report which of the three it is. "Disabled", "broken" and "never fired" look identical from the board and
have three different owners.

## What the owner actually asked for

When the owner says the fleet should keep working without prompting, the deliverable is a **live dispatch
mechanism**, not a longer explanation. Confirm your own tick is enabled and `Next run` is in the future, and
that is the end of the report: "tick is live at <interval>, next run <time>" beats a paragraph of diagnosis.
