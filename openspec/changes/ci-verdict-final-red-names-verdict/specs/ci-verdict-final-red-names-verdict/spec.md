# ci-verdict-final-red-names-verdict — a RED verdict's own final line says RED, never "no verdict" (issue #2222)

## ADDED Requirements

### Requirement: A RED verdict's final FAILED line says RED and never "no verdict"

The `ci-verdict` judge exits red for three distinct reasons: the judged run is genuinely red
(`verdict = red`, some selected job FAILED), it has no verdict (`none`, absent/skipped rows), or it
is green but the head carries blocking unjudged check-runs (#2116). The final stderr line —
`[ci-verdict] FAILED: run <id> has no verdict — see the summary line above...` — fired unchanged for
ALL of them, so a board quoting the LAST line of a genuinely-red verdict read "has no verdict" beside
the `linux/unit FAILED` line the summary had just named. That is the #2061 defect resurfacing one
layer lower: #2279 fixed the summary's own sentence; the exit-line still misspoke.

A red verdict, in particular, HAS a verdict — it is red. Its final line MUST therefore say the run is
RED and never contain `has no verdict`, while the NONE case keeps the #1111 wording (where "no
verdict" is exactly the point).

WHEN  `scripts/ci_verdict.py` exits red because `verify()` reached verdict `red`
THEN  the final `FAILED:` stderr line names the red verdict and does NOT contain `has no verdict`
      (the failing job(s) are named in the summary line it points to).

#### Scenario: a genuinely-red judged run ends with a RED line, not "no verdict"

Given run 42454987236's shape — a full-matrix decision, `linux / unit` FAILED, every other selected
job `success`, `verdict = red, failure = 1`,
When   `make ci-verdict` runs to a `failure` exit,
Then   the final stderr line contains `is RED ... FAILED` and does NOT contain `has no verdict`;
       the exit code stays 1 and the payload conclusion stays `failure`.
- **Test:** `tests/test_ci_verdict.py::test_a_red_verdicts_final_line_says_red_never_no_verdict`

#### Scenario: the exit message for a NONE verdict keeps the #1111 wording

Given the measured cancelled fan-out of run 41134761297 and no decision (verdict `none`),
When   `make ci-verdict` runs to a `failure` exit,
Then   the final stderr line retains `has no verdict — see the summary line above, which is what a
       board must quote instead of a failure count`.
- **Test:** `tests/test_ci_verdict.py::test_the_cli_exits_one_and_writes_a_failure_check_run_for_a_cancelled_run`

### Requirement: verdict, counts, summary lines, payload and exit codes are unchanged

The change is message-only to the final stderr line: the summary lines `verify()` produced, the
`verdict`/`counts`, the check-run payload and the process exit code SHALL be byte-identical to
before.

WHEN  any run is held to its decision with the same rows and decision as before this change
THEN  `verdict`, `counts`, the summary lines, the payload conclusion and the exit code are
      unchanged.

#### Scenario: the same rows still exit red with the same payload

Given run 41126873965's shape (full-matrix decision, `linux / unit` FAILED),
When   `make ci-verdict` runs with `CHECK_RUN_OUT` set,
Then   it exits 1, the payload conclusion is `failure`, and `verdict=red` is in the output.
- **Test:** `tests/test_ci_verdict.py::test_a_fully_settled_red_run_still_exits_one_through_the_settle_gate`

#### Scenario: a green decided skip still exits zero

Given a `tests/**`-class decision and a run whose unselected jobs were skipped,
When   `make ci-verdict` runs with `CHECK_RUN_OUT` set,
Then   it exits 0 and the payload conclusion is `success`.
- **Test:** `tests/test_ci_verdict.py::test_the_cli_exits_zero_and_writes_a_success_check_run_for_a_decided_skip`

### Requirement: an unjudged-red-forced failure names that cause, never "no verdict"

When the judged run is green but the head carries blocking unjudged check-runs (#2116), the verdict
is forced RED for a reason OUTSIDE the judged run: those unjudged rows are the cause. The final line
MUST say the head is red for that reason and point at the UNJUDGED RED lines, never `has no verdict`.

WHEN  `verify()` reaches `green` and `unjudged_reds` is non-empty, making the exit red
THEN  the final `FAILED:` stderr line names the unjudged-red cause, not `has no verdict`.

#### Scenario: a green judged run beside an unjudged red names the unjudged cause

Given the #1982 specimen — a green `CI` judged run beside a red `engine-build-pr-trigger`
check-run the verdict did not judge — and the verdict CLI reading the head's check-runs,
When   `make ci-verdict` runs to a `failure` exit,
Then   the final `FAILED:` stderr line names the unjudged-red cause and does not contain
       `has no verdict`.
- **Test:** `tests/test_ci_verdict.py::test_green_ci_beside_an_unjudged_red_is_not_posted_as_success`
