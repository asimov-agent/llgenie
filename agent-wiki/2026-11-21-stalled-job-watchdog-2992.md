# 2026-11-21 — stalled-job watchdog (issue #2992)

## What was verified against the spec

Issue #2992 measured the blind spot: PR #2990's CI run `44863652918` had every job
conclude within ~1 min except `linux/unit` (job `136722618230`), `in_progress` from
03:57:56Z with `updated_at` frozen at 03:57:57Z for 26 minutes (concluded 04:23:54Z).
While the run had no conclusion, `ci-verdict` never judged the head, the auto-merge
sweep never triggered on CI completion, and the reactor never fired — the stalled
conclusion silenced the whole landing chain. The existing monitors each miss the class:
`check_zero_job_pending.py` (zero-job runs only, #1410), `queued-alarm` (queued-state
jobs), `ci_frozen_reaper.py` (90-min frozen `updated_at`).

Implemented per the OpenSpec change `stalled-job-watchdog-2992`:

- `scripts/stalled_job_watchdog.py` — a run with at least one CONCLUDED sibling job
  plus an `in_progress` job older than `max(15 min floor, 1.25 x median wall time of
  that job name in the workflow's recent completed runs)`; 60-min named fallback when
  the job name has no history; 8 completed runs sampled per workflow. `--file` posts
  exactly one comment on the run head's PR ending with the dedupe marker
  `<!-- stalled-job-watchdog: run <id> job <job-id> -->`; a replay with the marker
  present posts nothing; a run with no PR is named in the report only. It never
  cancels and never re-runs (queue-pumping stays forbidden; cancel policy stays with
  the zero-job and frozen-reaper lanes).
- Wired as `make check-stalled-jobs` (mk/bots.mk, `.PHONY`) and as the first step of
  the `zero-job-pending.yml` lane — the lane already fires off ci-frozen-reaper
  completion, so the watchdog now runs every 2 hours against live runs.
- `tests/test_stalled_job_watchdog.py` (7 tests, `gh` stubbed on PATH, the #1410
  pattern): the measured wedge shape flagged once with elapsed + budget named; one
  comment exactly; within-budget unflagged (budget from the median, not the floor);
  marker replay silent; all-`in_progress` runs left to the other lanes; fallback
  budget without history; no-PR runs report-only. Live read-only smoke at this head:
  "no run has an in_progress job past its budget" (rc=0).

## Key decisions

- Budget is per JOB NAME from the workflow's own recent completed runs, so a
  legitimately long job is not flagged and a hung one is named within ~1 job-time
  instead of the frozen reaper's 90 minutes.
- Comment-only on purpose (the issue's How-we-fix-it item 3): naming while the run is
  live is the whole deliverable; cancel policy is out of scope and stays separated.
- The watchdog runs BEFORE the zero-job sweep in the lane: its exit contract is its
  own (0 nothing new / 1 findings without --file / 2 read failure / 3 delivery
  failure) and it must not be silenced by the zero-job path's failure.

## Current status

Fix commit + docs on `feat/stalled-job-watchdog-2992`; PR opened against main with
`closes #2992`; issue ACs ticked with replayable proofs at the PR head.
