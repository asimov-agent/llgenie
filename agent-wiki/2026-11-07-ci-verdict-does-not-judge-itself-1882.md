# ci-verdict does not judge its own posted check-run (#1882)

`ci-verdict` reds a **green** CI run by counting its own posted check-run as a failed job.
Measured on run `42275871131` @ head `cf88d285` (PR #1837, attempt 7): the CI run concluded
`success` — all 10 real jobs green — yet `GET /actions/runs/42275871131/jobs` returns an 11th
job named `ci-verdict` (id `128132878370`, conclusion `failure`, `workflow_name: "CI"`). That
row is the check-run `ci-verdict.yml`'s `judge` job POSTs to the head; GitHub attributes it back
into the judged run's job list.

`scripts/ci_scope.py::verify()` iterates the observed jobs, sees `ci-verdict` is not in the
10-job decision table, its conclusion is `failure`, and counts it → `verdict=red`. The first
failure came from an earlier stale state (guard FAILED before #1837's AC4 exemption); once the
check-run posted `failure`, that row stays in the run's job list, so every re-judge re-counts it
— a feedback loop no clean re-run of the judged PR can break.

Fix: `scripts/ci_verdict.py::main()` drops the job row named `CHECK_NAME` (`ci-verdict`) from the
observed set before calling `ci_scope.verify()`. The verdict does not judge itself — the
`ci-verdict` check-run is the report, not a gate. `ci_scope.py` and the decision table are
untouched; a real selected job that reports `failure` still reds. Regression test
`test_the_verdict_does_not_judge_its_own_posted_check_run`; 33 ci_verdict tests pass; the fix is
verified against the real reproduction data (run `42275871131` jobs + decision → `verdict=green`).