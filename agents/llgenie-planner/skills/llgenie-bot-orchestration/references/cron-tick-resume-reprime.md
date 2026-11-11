# Cron tick liveness: resumed is not re-primed

A paused scheduled tick is one way the orchestrator lane goes silently idle. Resuming it is not enough.

- `hermes cron resume <job_id>` flips the job `[active]` but does NOT recompute `next_run_at`; it stays stale/overdue from before the pause (seen: a job overdue by 4d 13h after resume).
- Fire one `hermes cron run <job_id>` to prime a fresh next-fire. That run executes a full agent pass and will exceed a 180s foreground timeout — do not wait on it; let it run, then poll the scheduler state.
- Confirm BOTH `[active]` and a current `next_run_at` in `hermes cron list`.

Pitfall: heartbeat/state files under the profile can update from a prior run while the job is paused. Never infer "a sweep is running" from heartbeat files alone — read the job's own `[active]`/`next_run_at` state.
