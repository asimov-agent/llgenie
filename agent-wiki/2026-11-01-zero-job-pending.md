# Zero-job-pending monitor (#1410)

A dispatched run whose workflow instantiates **zero jobs** stays `pending`/`queued` until cancelled,
and before this change no committed gate named it:

- `queued_run_alarm` (issue #254) scans a run's **job rows** — a zero-job run has none, so it
  renders "no job has been queued longer than 30 minutes" and reads clean.
- `run_failure_reactor` fires only on a run **conclusion** of `failure`/`cancelled`/`timed_out` — a
  `pending` run has `conclusion: null`, so it never reacts.
- `all_pipelines` treats `conclusion: null` as not-a-failure, and `ci_requeue` heals `cancelled`
  runs, not permanently-`pending` ones.

So a runner-starved dispatch (no large/self-hosted runner matches the requested labels; the pool
read 403 on this host) was indistinguishable from work-in-progress, forever.

## Evidence (2026-11-01)

Run `41321206783` (event `workflow_dispatch`, head `f41685f3`, `engine-build.yml`) was
`pending`/`queued` with `jobs.total_count == 0` from 15:26:09Z until cancelled 15:47:45Z. The
`engine-build-push` concurrency group was empty and the runner pool read returned 403. Nothing
named the run.

## What ships

- `scripts/check_zero_job_pending.py` — on `make check-zero-job-pending REPO=<owner/repo>`: lists
  the queued/in-progress runs, flags the ones past `--minutes` (default 30) with `jobs.total_count
  == 0`, names run id + head sha + created time. Exit 0 clean, 1 stuck, 2 read failed. `FILE=1`
  files **one deduped issue per stuck run** (idempotent by a run-id marker).
- `.github/workflows/zero-job-pending.yml` — a `workflow_run` reaction to `queued-alarm`
  (`types: [completed]`), `actions: read` + `issues: write`, `FILE=1`; never runs in a pull
  request, never merges. Trigger is REASONED, not inherited: the fleet's bot scheduled-minute
  budget is exhausted — every odd minute is owned, and the only three free odd minutes (`1`, `35`,
  `49`) are claimed by registry-liveness's resume (#1407 → #1416) — so a new `schedule:`-declaring
  workflow would collide with an existing bot (`test_no_workflow_shares_a_minute`, issues
  #275/#301). Riding queued-alarm's completion reuses its verified `:07/:37` cadence: the sibling
  stuck-run monitor's job-level sweep is followed by this run-level sweep. Like run-failure-reactor
  (issue #295), a `workflow_run` reaction is not startable by a human, so it carries no
  `workflow_dispatch` and no trigger guard.
- Mirrors the queued-alarm/registry-liveness monitor pattern (a control the board reads).

It complements (does not replace) `queued_run_alarm`: that reads the job pool's health, this reads
the liveness of any one dispatch.
