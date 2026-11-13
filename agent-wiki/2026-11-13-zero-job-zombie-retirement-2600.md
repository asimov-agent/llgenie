# zero-job zombie retirement (issue #2600, PR #TODO)

The five 2026-11-11 zero-job runs (43096752703, 43096752613, 43098130679,
43098130674, 43098130785) are phantoms: `gh run list` reports `queued,
conclusion=null, updated_at==created_at` (frozen at creation), the single-run
REST endpoint reports the same stale row, and only the cancel endpoint tells
the truth — `gh run cancel 43098130674` answers `Cannot cancel a workflow run
that is completed`. GitHub's designed cleanup (`DELETE /actions/runs/{id}`,
runs pending >24 h with no jobs) is admin-only and 403 for every identity this
monitor carries.

Measured 2026-11-13 on main `2180f3cec` before the change:
`make check-zero-job-pending CANCEL=1` printed 5 findings AND the cancel pass
`cancelled 0, 5 already concluded` — gate permanently red, and the #2584–#2588
issue spam was this mechanism re-facing the same rows daily.

Decision (OpenSpec `zombie-run-retire`): the cancel refusal is the truth
source. In fix mode, `already` RETIRES the candidate — no stranded issue, no
forced RED, no re-cancel — and `file_retirement_issue` files one deduped
record per run carrying the marker `<!-- zero-job-zombie-retired: run N -->`.
Every scan (any mode) reads retirement markers from issues open OR closed and
names those candidates zombie-retired: shown, never counted, never touched.
When every candidate this scan confirmed concluded AND all have records, the
findings set is empty and the gate exits 0; a failed record is DELIVERY FAILED
(exit 3), and cancel-only mode (no `--file`) stays red on purpose because the
confirmation cannot persist. A retirement record that already exists is not
re-filed (marker dedupe). Live starvation next to a zombie keeps the full
cancel + file + RED treatment (test-proven). Deleting the phantom rows
themselves is out of scope: filed as its own linked admin issue.

Spec: `openspec/changes/zombie-run-retire/` (validate green). Tests:
`tests/test_check_zero_job_pending.py` 17 green (4 new retirement tests; also
restored `test_a_zero_job_run_younger_than_the_threshold_is_not_flagged`, a
def line missing on main since #1410 — its body had been executing as dead
code inside the cross-branch test). Workflow flow comment updated.
