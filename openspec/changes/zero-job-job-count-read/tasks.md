# Zero-job job-count read — tasks

- [x] change the job-count expression to `len(jobs.get("jobs") or [])`
- [x] update the test stubs to emit the real `{"jobs":[...]}` shape (no `total_count`)
- [x] guard-prove: old code reds `test_a_run_with_jobs_is_not_flagged`, fixed code green (9/9)
- [x] change-note trio (agent-wiki + docs/changes.d + CHANGES.md) keyed to #1824
- [x] openspec spec + proposal + tasks
- [x] re-check #1823/#1822/#1709 against the fixed count (close, none names a real stranded run)
