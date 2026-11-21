# Name stalled `in_progress` CI jobs the whole-run monitors cannot see (issue #2992)

## Why

A run that is not frozen and not job-less is invisible to every existing monitor. Measured at
2026-11-21T04:23Z: run `44863652918` (auto-merge's trigger CI for PR #2990 head `8d4892e67`) had
every job conclude within ~1 min except `linux/unit`, which stayed `in_progress` from 03:57:56Z with
`updated_at` frozen at 03:57:57Z. The run kept `status=in_progress` until 04:23:54Z, so `ci-verdict`
(`workflow_run` on completion) never judged that head, `auto-merge.yml` (triggered by the verdict's
completion) never armed the merge, and the merge sweep deferred the head on the absence of any verdict
row at it. The issue-bot recheck sweep then compounded the wedge by re-pushing the stale red verdict
onto the fresh head (issue #2991, landed separately). No existing monitor named it:
`queued_run_alarm` needs a job queued in the `queued` state (this job is `in_progress`);
`check_zero_job_pending.py` covers zero-job runs (#1410) and the stranded-queue wedge (#917) — a run
with jobs is not its finding; `ci_frozen_reaper.py` requires `updated_at` to sit ≥90 min — this run
refreshed `updated_at` more often and resolved at 26 min; the reactor needs a conclusion the run
never reached. A ~1 min trigger-CI run that idles 26 minutes is a defect worth naming the moment it
crosses a job-specific budget, before it silently blocks the merge chain.

## What Changes

- New `scripts/stalled_job_watchdog.py`: scans `in_progress` runs and flags a job when the run has at
  least one CONCLUDED job (so the run is demonstrably not queued-starved or job-less) and an
  `in_progress` job has been running past a named budget: `max(STALL_FLOOR=15 min, STALL_FACTOR=1.25 ×
  median wall time of that job's name in the same workflow's recent completed runs)`; when the job name
  has no history, the budget falls back to `FALLBACK_MINUTES=60`. A run whose every job is still
  `in_progress` is NOT flagged — that is the frozen/queued lanes' domain.
- `--file` posts exactly one issue comment on the PR whose head the run carries, naming the job, its
  elapsed minutes, the budget and its derivation, and the run link; the comment carries the dedupe
  marker `<!-- stalled-job-watchdog: run <id> job <job-id> -->` and a replay after a delivered comment
  posts no second one. A run with no PR (push/schedule) is named in the report only — no issue filing.
- The watchdog NEVER cancels, cancels nothing, and reruns nothing (issue #2992 out of scope; the
  zero-job and frozen lanes keep the cancel policy).
- `make check-stalled-jobs` (mk/bots.mk) wraps the script; `.github/workflows/zero-job-pending.yml`
  runs it as a step beside the zero-job gate on the same lane trigger, so the class is named within one
  monitor pass of the stall.
- `tests/test_stalled_job_watchdog.py` pins: AC1 the measured shape (one concluded job + one stalled
  `in_progress` job past budget) flags exactly once naming the job and the elapsed time; AC2 an
  `in_progress` job within budget flags nothing; AC3 a replay with the marker already on the PR posts
  no second comment; plus: all-`in_progress` runs are left to the other lanes, the no-history fallback
  budget, and the exit-code contract (0 clean / 1 findings unpresented / 2 read failure / 3 delivery
  failure).

## Impact

- `scripts/stalled_job_watchdog.py` — new monitor module.
- `tests/test_stalled_job_watchdog.py` — new tests with a `gh` stub on PATH (the #1410 pattern).
- `mk/bots.mk` — `check-stalled-jobs` target.
- `.github/workflows/zero-job-pending.yml` — one new step; header Flow line updated.
- `docs/BOTS.md` — regenerated index row; `agent-wiki/` + `docs/changes.d/` work records.
- Not covered (its own linked issue, filed at landing): cancelling or capping stalled runs — the cancel
  policy stays with the frozen-reaper/zero-job lanes.

Refs: issue #2992 (Problem/Why/fix/AC with the measured ids).
