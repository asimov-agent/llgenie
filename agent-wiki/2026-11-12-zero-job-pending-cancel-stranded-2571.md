# Zero-job-pending cancel-stranded — the monitor now clears the zombies it names (#2571)

Issue: #2571 · out-of-scope: #2570 · branch: feat/engine-build-pending-purge

## What was verified

- **The measured defect.** `scripts/check_zero_job_pending.py` (issue #1410, discriminator #1704)
  names stranded zero-job runs (files one deduped issue, forces the head RED) but clears nothing,
  and its already-filed dedupe skips FILING only — so a named run is skipped by every later monitor
  run and GitHub never evicts it. On `origin/main` `e6b9b4b4f`: the 08:23Z monitor run filed
  #2520-#2525 naming six stranded runs (created 2026-11-11 20:33Z/20:47Z on merged PRs
  #2500/#2507). At 11:12Z (14.6h later) five were still `queued` with `jobs.total_count == 0` and
  `updated_at` frozen at creation (43096752613, 43096752703, 43098130674, 43098130679, 43098130785);
  `gh run cancel --force` refused 43096752703 claiming the run "is completed" while the list
  endpoint still showed it `queued`. The 6th (43096752585) sat `in_progress` with zero jobs for
  ~15h, its one job ending only as `failure`. A full-matrix engine-build push sweep (43203422414,
  queued 10:47Z, `push=true`) was cancelled at 11:06Z having never instantiated an engine job.
- **The permanent fix.** `scripts/check_zero_job_pending.py` gains `--cancel-stranded`: BEFORE
  name-and-file, `cancel_stranded()` CANCELs every classified stranded run — including
  already-filed ones — re-reading the run's jobs at cancel moment and SKIPping when jobs
  instantiated (a runner finally arrived; the #1822/#1823 never-kill-a-live-run rule). Four
  outcomes: `cancelled` / `skipped` / `already` (GitHub already concluded it mid-call — a benign
  race, never a delivery failure) / `failed`. `_how_steps()` makes the filed body state the remedy
  that actually happened. Cancelling first lets the body describe reality.
  `gh run cancel <id> --force` covers the queued/completed API disagreement.
- **Wired unattended.** `Makefile` turns `CANCEL=1` into `--cancel-stranded` on
  `check-zero-job-pending` (mirrors the `FILE` knob); `.github/workflows/zero-job-pending.yml`
  runs `FILE=1 CANCEL=1` and holds `actions: write` for `POST /actions/runs/{id}/cancel`.
- **Tests.** Four new scenario tests in `tests/test_check_zero_job_pending.py`: an already-named
  zombie is cancelled without a second issue or re-RED; a run whose runner arrived between
  classification and cancel is NOT cancelled (skip stated in summary and body); a queued-behind
  sibling is never reported/filed/cancelled and cancel-only mode files nothing; a cancel racing a
  concluded run counts `already` with no DELIVERY FAILED. Module: 13/13 pass (rc=0).

## Current status

OpenSpec change `zero-job-pending-cancel-stranded`; verification (pytest, `make check-wiring`,
`make openspec-validate`, `make lane-preflight`) recorded in the PR. The unattributed engine-build
queue kill (queued push sweep 43203422414 cancelled 9s after an unexplained re-dispatch
43206254966) is tracked separately as #2570.
