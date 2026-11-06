# ci-verdict-does-not-judge-itself

## ADDED Requirements

### Requirement: the verdict does not judge its own posted check-run

`scripts/ci_verdict.py::main()` MUST NOT pass a job row named `CHECK_NAME` (`ci-verdict`) to
`ci_scope.verify()`. GitHub attributes the check-run `ci-verdict.yml`'s `judge` posts back into
the judged run's job list, so a `ci-verdict` row in the observed set is the verdict's own report,
not a gate — counting it reds a run whose real jobs are all green.

WHEN a finished run's job list contains a `ci-verdict` row alongside its real jobs
THEN the verdict ignores that row and judges only the jobs the decision table names

#### Scenario: a green run with its own ci-verdict row judges green

- **Given** a full-matrix decision, the 10 real jobs all `success`, and an 11th row named
  `ci-verdict` with conclusion `failure` (the posted check-run, measured run `42275871131`)
- **When** `ci_verdict.py::main()` runs against those jobs
- **Then** it exits 0 and posts a `success` check-run whose summary is `verdict=green` with the
  `ci-verdict` row not counted as a failure
- **Test:** `tests/test_ci_verdict.py::test_the_verdict_does_not_judge_its_own_posted_check_run`

### Requirement: the real jobs are still judged

The fix MUST NOT swallow a genuine failure: a real job the decision selected that reports
`failure` still reds the verdict.

WHEN a real selected job reports `failure` alongside the `ci-verdict` row
THEN the verdict is still red and names that job

#### Scenario: a real failure is not masked

- **Given** a decision selecting `linux/unit`, a `ci-verdict` row, and `linux/unit` reported
  `failure`
- **When** `ci_verdict.py::main()` runs
- **Then** the verdict is red and names `linux/unit`
- **Test:** `tests/test_ci_verdict.py` existing red-run cases (unchanged)