# ci-verdict manual re-judge via workflow_dispatch (#1886)

`.github/workflows/ci-verdict.yml` is `workflow_run`-triggered only: it judges a finished CI run when
that run completes. There was no `workflow_dispatch`, so the only way to re-judge a previously-red
run was to re-run the **whole heavy CI fan-out** — and once GitHub pushed a finished run's job
records past retention (`GET /actions/runs/{id}/jobs` → `total_count` shrinks to a handful, measured
on run `42275871131` @ `cf88d285`, PR #1837), the judge correctly posted `none` ("N job(s) ABSENT")
because the real rows were gone, not because the run was green. A legitimate run whose verdict was red
for a reason that has since cleared could never be re-judged green.

Fix: `ci-verdict.yml` now also declares a `workflow_dispatch` with a required `run_id` input and an
optional `head_sha`. The `judge` job resolves `RUN_ID`, `HEAD_SHA` and the concurrency group key from
`inputs.*` when dispatched, else from `github.event.workflow_run` — so the auto path is unchanged.
The dispatch runs the same `judge` steps: read the named run's jobs + `ci-scope-decision` artifact,
`make ci-verdict`, post the fresh check-run. It never re-runs the judged run, edits no branch, and
reads no secret (permissions stay `contents: read, actions: read, checks: write`). An operator can now
re-judge one finished run by name without paying the CI fan-out or losing a run to job-record expiry.
