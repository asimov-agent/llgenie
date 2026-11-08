# ci-requeue-nonretryable

## MODIFIED Requirements

### Requirement: GitHub's refusal to retry a cancelled run is a skip, never a fatal error

`scripts/ci_requeue.py` must NOT red the healer because GitHub decided a run cannot be retried. A cancelled
run with zero jobs instantiated (`/jobs` `total_count == 0`) is classified non-retryable at `plan()` and
landed in the skip bucket without a dispatch; a `gh run rerun` whose stderr carries a `NON_RETRYABLE_MARKERS`
phrase (`cannot be retried` / `cannot be rerun`) is recorded as skipped at `rerun()` and the sweep continues
to exit 0. Every OTHER non-zero `gh run rerun` return — rate limit, 5xx, auth — remains a fatal error that
aborts the sweep non-zero, so a real problem is never swallowed.

#### Scenario: a cancelled run with no jobs is skipped at plan

Given a cancelled run (e.g. a `workflow_dispatch` engine-build run) whose `/jobs` listing has
`total_count == 0`,
When `plan(repo, window)` classifies it alongside other runs in the window,
Then it lands in the SKIP bucket with reason `no jobs instantiated: GitHub will not retry this run` and NO
`gh run rerun` is dispatched.
- **Test:** `tests/test_ci_requeue.py::test_a_cancelled_run_with_no_jobs_is_skipped_at_plan`

#### Scenario: a run GitHub refuses to retry is recorded skipped, not failed

Given a cancelled run on which the runtime calls `gh run rerun --failed` and GitHub answers
`This workflow run cannot be retried` (non-zero),
When `rerun(repo, run, dry=False)` runs,
Then it records the run as skipped with the refusal as its reason and the sweep continues, re-runs the
still-retryable siblings, and exits 0.
- **Test:** `tests/test_ci_requeue.py::test_a_run_github_refuses_to_retry_is_skipped_not_failed`

#### Scenario: a genuinely transient rerun failure stays fatal

Given a cancelled run on which `gh run rerun --failed` fails with an unrelated error (e.g. `API rate limit
exceeded`),
When `rerun(repo, run, dry=False)` runs,
Then it raises `SystemExit` non-zero naming the real cause — a real problem is never swallowed by the
refusal skip.
- **Test:** `tests/test_ci_requeue.py::test_a_transient_rerun_failure_is_still_fatal`

#### Scenario: a dry run names the non-retryable run in the skip bucket

Given a window containing a zero-job cancelled run,
When `ci_requeue.py run --dry` (or `plan`) runs,
Then it prints that run in the keep/skip list with its reason and dispatches nothing.
- **Test:** `tests/test_ci_requeue.py::test_plan_dry_puts_a_zero_job_run_in_the_skip_bucket`
