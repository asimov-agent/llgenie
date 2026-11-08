# guard-body-red-does-not-hide-code-fanout — a guard body-red measures the code fan-out and names its gate (issue #2285)

## ADDED Requirements

### Requirement: the code fan-out runs when the guard reds on a PR-body text gate

When `guard` fails on a PR-BODY gate (check-pr-acceptance-form / check-pr-acceptance), GitHub's
`needs:` default would skip every dependent including the `linux` call that carries the ONLY code
measurement (`linux / unit` + `linux / openspec`). A body red must therefore NOT suppress those two
jobs: the `linux` call must still start (running no top-tier stage), so a head whose only red is a
text gate answers the code question at the same head.

WHEN  a CI run is a pull_request whose `guard` job failed with a non-zero body-text gate,
THEN  the `linux` caller still runs its `linux / unit` and `linux / openspec` rows (conclusion
      `success`/`failure`, never `skipped`), and its top-tier axis is the `["none"]` placeholder.

#### Scenario: a guard body-red keeps the code gate measured

Given a head whose guard fails on `check-pr-acceptance-form` (the body carries no `## Acceptance
criteria`), and a diff that is a code change,
When   `.github/workflows/ci.yml`'s `linux` call is scheduled,
Then   it is NOT skipped (its `if` overrides the needs-skip on a guard body-red) and it still
       consumes `needs.guard.outputs.top_tier_rows` with a fallback.
- **Test:** `tests/test_ci_images.py::test_only_linux_calls_the_pipeline_file_and_no_macos_runner_is_requested` +
  `tests/test_ci_slow_rows.py::test_ci_yml_publishes_the_decision_and_the_caller_consumes_it`

#### Scenario: a real ci-images failure still stops the fan-out

Given a CI run whose `ci-images` job truly FAILED,
When   the `linux` call's `if` is evaluated,
Then   the call is skipped (a genuine image-build red does not start the code fan-out), so a real
       build failure is not masked by an empty matrix.
- **Test:** `tests/test_ci_images.py::_job_if_allowed` (the exact `if:` is allowlisted as the one
  needs-override that runs a guard-gated call, never a skip)

### Requirement: an ABSENT row whose gate failed is named as blocked, never anonymous

A matrix row that never reported while its gate (`guard`, or the `linux` caller for a `linux/*`
child) was observed non-success is a consequence of that gate, not an independent mystery. It must
be counted and named separately from an honest no-verdict, so the summary never buries the cause.

WHEN  a row the decision selected is ABSENT or non-success and its gate's observed states are not
      all `success`,
THEN  its line names the gate (`ABSENT — blocked by linux skipped` / `skipped — blocked by guard
      failure`), the count is `blocked`, and the verdict is RED when a gate failure exists.

#### Scenario: guard failure blocks its dependents and names them

Given run 42515444174's shape (guard FAILED; ci-images/scanner-images/linux skipped; every
`linux/*` absent) and a full-matrix decision,
When   `scripts/ci_scope.py::verify` is run,
Then   the verdict is `red`, `counts["failure"]` is 1, `counts["blocked"]` is 9, every blocked row
       names its gate, and no `NO VERDICT: ... 0 failures is not a verdict` sentence is printed.
- **Test:** `tests/test_ci_verdict.py::test_a_guard_body_red_names_the_gate_it_blocked_and_is_a_named_red_not_no_verdict`

#### Scenario: a child blocked by its own skipped caller names the caller, not the guard

Given a clean guard (success) and the `linux` caller skipped,
When   `verify` is run,
Then   no `linux/*` child names the guard (it is not non-success); each is blocked by `linux
       skipped`, and the verdict stays `none` because nothing failed.
- **Test:** `tests/test_ci_verdict.py::test_a_failed_linux_caller_child_is_blocked_by_the_caller_and_a_clean_gate_row_stays_unaccounted`

### Requirement: an honest no-verdict keeps the #1111 sentence

A row absent while BOTH its caller and the guard are clean is a genuine gap nobody's failure
explains. That is exactly the case that must keep the #1111 wording.

WHEN  a selected row is ABSENT and no gate is observed non-success,
THEN  it is counted `no_verdict` and the summary may print `NO VERDICT: ... 0 failures is not a
      verdict` (zero failures is the point).

#### Scenario: a clean gate leaves an absent child an honest no-verdict

Given guard=success, linux=success, and a `linux/*` child that never reported,
When   `verify` is run,
Then   that child is counted `no_verdict` (not blocked), and the #1111 sentence appears.
- **Test:** `tests/test_ci_verdict.py::test_a_failed_linux_caller_child_is_blocked_by_the_caller_and_a_clean_gate_row_stays_unaccounted`

### Requirement: a RED verdict names its failing jobs and its blocked count

A verdict that is RED must state the failing job(s) and the rows its failed gate blocked — never a
"0 failures" sentence that contradicts the `guard FAILED` line printed above it, and never an
anonymous counter that hides a guard (issue #2061 + #2285).

WHEN  `counts["failure"] >= 1`,
THEN  the summary's final line states `RED: N job(s) FAILED (<cause>); M blocked by a gate;
      O unaccounted; P pending` and never contains `0 failures is not a verdict`.

#### Scenario: the measured guard-body-red run prints a named RED, not NO VERDICT

Given the exact measured fan-out of run 42515444174 and the post-workflow-fix code rows present,
When   `verify` is run,
Then   the code matrix is measured (success rows), the guard is the named cause, the two image rows
       are `blocked by guard failure`, and no `0 failures / NO VERDICT` sentence is emitted.
- **Test:** `tests/test_ci_verdict.py::test_a_guard_body_red_with_the_code_matrix_run_still_names_the_guard_and_measures_code`
