# ci-verdict-dispatch-rejudge

## Why

Re-judging a previously-red `ci-verdict` run currently requires re-running the **whole heavy CI
fan-out**. `ci-verdict.yml` is `workflow_run`-triggered only (no `workflow_dispatch`), so the only way
to get the judge to look again is to re-run the judged `CI` run — re-firing `guard`, `ci-images`,
`scanner-images` and every `linux` job just to regenerate job rows the small `judge` job reads back.
Worse, GitHub **expires** a finished run's job records (`GET /actions/runs/{id}/jobs` →
`total_count` shrinks), after which the judge correctly posts `none` ("job(s) ABSENT") because the real
rows are gone — a legitimate run whose verdict was red for a reason that has cleared can never be
re-judged green. Measured 2026-11-06: run `42275871131` @ `cf88d285` (issue #1882 fallout, PR #1837)
had expired to `total_count: 1` by re-judge time; the post-fix fresh check-run `128153241467` read
"10 job(s) ABSENT".

## What changes

Add a manual re-judge path: a `workflow_dispatch` on `ci-verdict.yml` with a `run_id` input (plus an
optional `head_sha`) that runs the **same `judge` steps** as the `workflow_run` path against the named
finished run. `RUN_ID`, `HEAD_SHA` and the concurrency group key resolve from the dispatch input when
present, else from `github.event.workflow_run` — the auto path is unchanged. The manual path reads
only that run's jobs + decision and posts a fresh check-run; it does not re-run the judged CI and
edits nothing. The header "Never: dispatches, re-runs or merges anything" becomes "never re-runs or
merges; the one dispatch exception is a manual re-judge".

## Out of scope

- Any change to `scripts/ci_verdict.py` or to what the judge decides.
- Any change to the `workflow_run` auto-judge behaviour or its concurrency semantics.
- A UI/CLI wrapper or scheduler — this is the workflow trigger only.
