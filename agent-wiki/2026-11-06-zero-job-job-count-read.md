# 2026-11-06 zero-job-pending job-count read made truthful (issue #1824)

`check_zero_job_pending.py` decided "does this run have zero jobs?" with
`total = int((jobs.get("total_count") if isinstance(jobs, dict) else None) or 0)` after
`gh run view <rid> --json jobs` — but that projection returns `{"jobs": [...]}` with **no
`total_count` key**, so the expression always evaluated `None or 0` → `0` for *every* run.
A run with three live jobs (run `42141213441`: `guard` + `matrix` + `engine-build-vllm-rocm`)
read as "zero jobs", and any in-progress run past the `--minutes` threshold was mis-filed as a
stranded "no runner matched the labels" work item.

The fix counts the jobs **array** (`total = len(jobs.get("jobs") or [])`) instead of a key the
projection never emits. A run whose jobs array is non-empty has instantiated jobs and is never the
zero-job case, however long it has run (a live 2h compile is not a stall). A genuinely jobless
stranded dispatch is still filed exactly as before — the discriminator against the
queued-behind-concurrency class (#1704) is untouched.

Effect on the three known filings: #1823 (run 42141213441, total_count 3), #1822 (run 42133077000,
total_count 2), #1709 (run 41865249927, total_count 2) are all false positives under the true count
and are re-checked/closed against the fixed read. Verified: old code reds
`test_a_run_with_jobs_is_not_flagged` (rc 1), fixed code is green (9/9).
