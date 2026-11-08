# ci-verdict-red-names-failing-jobs — a RED summary names the failing jobs, never "0 failures" (issue #2061)

## ADDED Requirements

### Requirement: A RED verdict names the jobs that failed

When a run's own `guard` job fails, every selected row is skipped or absent and
`counts["failure"] = 1`, so the #1111 sentence `0 failures is not a verdict` — written for a run
with *zero* failures — directly contradicts the `guard FAILED` line printed above it, and a board
quotes "0 failures" for a red run. A non-green verdict with at least one failure MUST therefore state
that failure in its own final line, while a non-green verdict with zero failures keeps the #1111
sentence (where zero is the point).

WHEN  a run is held to its scope decision and the verdict is `red` (`counts["failure"] >= 1`)
THEN  the summary ends with a line that names the failing job(s) and never contains the wording
      `0 failures is not a verdict`.

#### Scenario: a guard failure is named as the cause

Given a run whose own `guard` job FAILED and the selected rows skipped/absent, and no decision,
When   `scripts/ci_scope.py::verify` is run,
Then   the verdict is `red`, `counts["failure"]` is 1, and the final summary line reads
       `RED: N job(s) unaccounted for — 1 FAILED (guard), M unaccounted, 0 pending` and contains no
       `0 failures is not a verdict` wording.
- **Test:** `tests/test_ci_verdict.py::test_a_failed_guard_is_named_as_the_cause_never_zero_failures`

#### Scenario: a guard failure with a decision is still a named red through the CLI

Given a full-matrix decision and the same guard-failed run,
When   `make ci-verdict` runs with `CHECK_RUN_OUT` set,
Then   it exits 1 (a red verdict), the output names `1 FAILED (guard)`, and the payload conclusion
       is `failure`.
- **Test:** `tests/test_ci_verdict.py::test_a_guard_failure_with_a_decision_is_a_named_red`

### Requirement: A NONE verdict keeps the #1111 sentence

Zero failures with absent/skipped rows is the exact case #1111 wrote the sentence for: the count is
zero, and that IS the point. The wording must not change for a `none` verdict.

WHEN  a run is held to its scope decision and the verdict is `none` (`failure == 0` with unaccounted
      rows)
THEN  the summary ends with `NO VERDICT: N job(s) unaccounted for — 0 failures is not a verdict`,
      unchanged.

#### Scenario: a cancelled fan-out with no failures keeps the #1111 sentence

Given the measured cancelled fan-out of run 41134761297 and no decision artifact,
When   `verify` is run,
Then   the verdict is `none` and the summary contains `0 failures is not a verdict`.
- **Test:** `tests/test_ci_verdict.py::test_a_cancelled_fan_out_with_no_decision_is_never_green`

### Requirement: verdict, counts and exit code are unchanged

The message split must never alter a verdict decision: the same rows produce the same `verdict`,
`counts` and process exit code as before the change.

WHEN  any run is held to its decision and its rows and decision are the same as before this change
THEN  `verdict`, `counts` and the exit code are byte-identical.

#### Scenario: a fully green decided run is unchanged

Given a `tests/**`-class decision and a run whose unselected jobs were skipped,
When   `verify` is run,
Then   the verdict is `green`, every legitimate skip is `skipped-by-decision`, and no non-green
       summary line is added.
- **Test:** `tests/test_ci_verdict.py::test_a_skip_the_decision_made_is_green_and_counted`
