# ci-verdict-does-not-judge-itself

## Why

`ci-verdict` reds a **green** CI run by counting its own posted check-run as a failed job
(measured on run `42275871131` @ `cf88d285`, issue #1882). `ci-verdict.yml`'s `judge` posts a
check-run named `ci-verdict` to the head, and GitHub attributes that posted check-run back into
the judged run's job list (`workflow_name: "CI"`). `ci_scope.verify()` then sees a `ci-verdict`
job that is not in the 10-job decision table, concludes `failure`, and reds a run whose real
jobs are all green — a feedback loop (once red, every re-judge re-counts it, so no clean re-run
of the judged PR can break it).

## What changes

`scripts/ci_verdict.py::main()` drops the row named `CHECK_NAME` (`ci-verdict`) from the
observed job set before calling `ci_scope.verify()`. The verdict does not judge itself: the
`ci-verdict` check-run is the report, not a gate. `ci_scope.py` and the decision table are
untouched.

## Out of scope

- Any change to what the decision selects or to `ci_scope.verify()`'s accounting of real jobs.
- The earlier stale-state failures (guard FAILED before #1837's AC4 exemption) that first posted
  the red check-run — this change stops the re-counting; the re-judge then posts green.
