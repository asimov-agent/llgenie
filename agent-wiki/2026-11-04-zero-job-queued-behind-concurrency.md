# reactor: a zero-job run queued behind its concurrency group is not "no runner matched" (#1704)

`scripts/check_zero_job_pending.py` flagged any `queued`/`in_progress` run with `jobs.total_count == 0`
as a **#1250-class no-runner door**: engine-build serialises per engine×arch concurrency group (#917,
`cancel-in-progress: false`), and a later `workflow_dispatch` legally waits with zero jobs until its
turn. The detector's single signal could not tell a run **waiting** (will start) from a run **stranded**
(never starts, no runner will ever take it), so 6 of 6 filings were false positives (#1473 / #1536 /
#1569 / the #1699-#1701 set), each closed as a one-off while the genuine stranded case was never gated.

The detector now discriminates by concurrency holder: `zero_job_pending_runs` first collects the
(workflow, branch) pairs of `in_progress` runs — the runs actually holding a group — then skips a
**queued** candidate whose pair is held: that run is waiting its turn, not short of runners. An
`in_progress` run with zero jobs is itself the stalled one (it took the group and still instantiated
nothing) and stays a candidate, so the no-runner door is unchanged for real stranding. The `--json`
run-list field set gains `status` for the classifier.

Prove-the-guard: two new tests plant the queued-behind-group case (queued run suppressed, in_progress
holder flagged) and the cross-branch-holder case (a same-workflow run on its own branch is NOT treated
as behind main's sibling and stays flagged); a genuinely stranded in_progress run stays by
construction. import-roots ratchet holds at the recorded baseline; reactor/verdict/frozen suite green.
No gate weakened — the skip is classification, never a pass-through.

FORCED RED (the second half of #1704's acceptance): a STRANDED run stays `pending` — GitHub does not
fail a run whose workflow instantiates no jobs, so neither `queued_run_alarm` (scans job rows, none)
nor `run-failure-reactor` (needs a failure/cancelled conclusion) sees it, and `ci-verdict`'s own
`workflow_run: [completed]` hook never fires because the run never completes. `--file` now forces the
stranded run's head RED via the same `ci-verdict` check-run payload `scripts/ci_scope.py` posts
(`check_run_payload(RED, head, ...)` → `conclusion: failure`), so a genuinely-unrunnable dispatch
surfaces as a failed check with a reason instead of an eternal `pending` that reads like a working
matrix — and the monitor workflow gains `checks: write` so the check-run can land. Idiomatic: a run
whose marker is already in an open issue is neither re-filed nor re-forced RED. Implements #1704.
