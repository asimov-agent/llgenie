# zero-job-pending-cancel-stranded

## Why

`scripts/check_zero_job_pending.py` (issue #1410, discriminator #1704) detects stranded zero-job runs,
files one deduped issue per run, and forces the run's head RED — but it has no clearing action, and its
`--file` loop SKIPS any already-filed run entirely (line ~281: `if already_filed(...): continue`). A
stranded run is therefore named once and then left pending forever: every later monitor run sees the
marker, skips the run, and the scheduler never evicts it on its own.

Measured 2026-11-12 on `origin/main` `e6b9b4b4f`: the 08:23 monitor run filed issues #2520-#2525 naming
SIX stranded runs created 2026-11-11 20:33Z/20:47Z on branches `feat/2472-semgrep-ghost-runs` and
`feat/engine-bump-regen-guard`. Both PRs (#2500, #2507) merged at 22:02Z/22:08Z the same evening — the
runs belong to merged heads and can produce nothing. At 11:12Z (14.6h later) five of the six were still
`queued` with `jobs.total_count == 0` and `updated_at` frozen at creation (43096752613, 43096752703,
43098130674, 43098130679, 43098130785); `gh run cancel --force` refused them claiming the run
"is completed". The 6th (43096752585) sat `in_progress` with zero jobs for ~15h and its one job
(`ci-verdict`) ended only as a `failure`. A full-matrix engine-build push sweep (43203422414, queued
10:47Z) was cancelled at 11:06Z having never instantiated an engine job — the zombies hold queue
capacity live work needs.

## What Changes

- Add `--cancel-stranded` to `scripts/check_zero_job_pending.py`: BEFORE the name-and-red step, CANCEL
  every stranded run — including already-filed ones (the skip at line ~281 protects against re-filing,
  not against clearing; a run named yesterday is still a zombie today). Cancelling first lets the filed
  body state the outcome that actually happened.
- Re-read each run's jobs immediately before cancelling; if jobs instantiated (a runner finally
  arrived), SKIP the cancel — the #1822/#1823 class (a live compile must never be touched).
- Wire the clearing action into the unattended monitor: `zero-job-pending.yml` passes `CANCEL=1` to
  `make check-zero-job-pending`, and the Makefile turns `CANCEL=1` into `--cancel-stranded`.
- Amend the filed issue's `How we fix it` so the automatic remedy is stated (the monitor cancels
  stranded zero-job runs; re-dispatch once a runner exists), not only the manual one.

## Impact

- Affected specs: `zero-job-pending` (ADDED requirement: stranded runs are cleared, not only named)
- Affected code: `scripts/check_zero_job_pending.py`, `Makefile` (target `check-zero-job-pending`),
  `.github/workflows/zero-job-pending.yml`, `tests/test_check_zero_job_pending.py`
- Affected docs: `agent-wiki/2026-11-12-zero-job-pending-cancel-stranded-2571.md`,
  `docs/changes.d/2026-11-12-zero-job-pending-cancel-stranded-2571.md`
