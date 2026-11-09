# ci-requeue-nonretryable — tasks

- [x] `scripts/ci_requeue.py::NON_RETRYABLE_MARKERS` names the rejected-retry stderr phrases (`cannot be retried`, `cannot be rerun`)
- [x] `scripts/ci_requeue.py::_gh_no_raise` captures a `gh run rerun` non-zero return + stderr instead of aborting
- [x] `scripts/ci_requeue.py::_job_count` reads a run's `/jobs` `total_count` (0 = nothing instantiated → non-retryable), returning -1 on a failed probe so the runtime still classifies
- [x] `scripts/ci_requeue.py::plan` skips a cancelled run with zero jobs as `no jobs instantiated: GitHub will not retry this run` (the DRY classifier, no dispatch)
- [x] `scripts/ci_requeue.py::rerun` returns `"skip"` (recorded, sweep continues, exit 0) when GitHub's refusal marker is present; returns `"reran"` on success / `"dry"` under `--dry`; RAISES on any other non-zero return
- [x] `scripts/ci_requeue.py::main` routes a runtime `"skip"` into the skip bucket so the summary and exit agree
- [x] `tests/test_ci_requeue.py::test_a_cancelled_run_with_no_jobs_is_skipped_at_plan` — zero-job run is skip-bucketed at plan without a rerun call
- [x] `tests/test_ci_requeue.py::test_plan_dry_puts_a_zero_job_run_in_the_skip_bucket` — `run --dry` prints it in the keep/skip list, dispatches nothing
- [x] `tests/test_ci_requeue.py::test_a_run_github_refuses_to_retry_is_skipped_not_failed` — runtime refusal records SKIPPED and still re-runs the retryable sibling, exit 0
- [x] `tests/test_ci_requeue.py::test_a_transient_rerun_failure_is_still_fatal` — negative control: a rate-limit/5xx still aborts non-zero
- [x] `Makefile` `ci-requeue-cancelled` `##` help states the refusal-skip contract (issue #2295)
- [x] `docs/BOTS.md` re-states the refusal-skip contract beside the `ci-requeue-cancelled` make-help line
- [x] change-note trio: `agent-wiki/2026-11-08-ci-requeue-nonretryable-2295.md`, `docs/changes.d/2026-11-08-ci-requeue-nonretryable-2295.md`, `CHANGES.md` regenerated via `make changes-index`
- [x] full `tests/test_ci_requeue.py` green (18 passed incl 4 new)
