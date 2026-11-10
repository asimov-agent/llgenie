# acceptance-gate-circular

## ADDED Requirements

### Requirement: the acceptance gate classifies a self-gating criterion as `gate-circular`, a distinct non-blocking finding

`make check-pr-acceptance` (`scripts/check_pr_acceptance.py`) MUST, when it reads a linked issue's
unticked `## Acceptance criteria` box whose criterion demands the acceptance gate's OWN job verdict be
green, report it as `gate-circular` — a distinct finding whose `blocking` is false, with a message
naming the loop — rather than `acceptance-unchecked`. A criterion is self-gating when it names the
gate's own footprint: the unambiguous identifiers `check-pr-acceptance`, `check-pr-acceptance-form`,
`ci-verdict`, or `ci-scope-decision`, or the CI JOB names `guard job` or `judge job` (a product noun
like a "quota guard" is never the gate's own job and MUST NOT be trapped). The `## Not covered` +
linked `#<n>` exemption (issue #1792) MUST still win over the classification when present. The gate
MUST exit non-zero when a BLOCKING finding exists and zero when the only findings are `gate-circular`
(or `proven-awaiting-writer`).

WHEN a PR that `closes #N` closes issue `#N` with an unticked criterion naming the gate's own job
verdict (e.g. "the guard job that runs check-pr-acceptance is green in the fixing PR's CI run"),
AND the criterion is not named out of scope,
THEN the gate reports `gate-circular` (distinct, non-blocking, exit zero once peer criteria are proven)
AND never `acceptance-unchecked` for that criterion.

#### Scenario: a guard-verdict criterion is classified gate-circular and does not red

- **Given** a PR closing an issue whose `## Acceptance criteria` has a criterion "the guard job that
  runs check-pr-acceptance is green in the fixing PR's CI run" as its only unticked item
- **When** `make check-pr-acceptance` runs
- **Then** it reports `gate-circular`
- **And** the finding is non-blocking, so the close exits zero once the other criteria are proven
- **Test:** `tests/test_check_pr_acceptance.py::test_criterion_demanding_the_gate_own_verdict_is_GATE_CIRCULAR_not_unchecked`
- **And:** `tests/test_check_pr_acceptance.py::test_gate_circular_close_is_not_red_once_other_criteria_are_proven`

#### Scenario: the render labels the gate-circular finding distinctly

- **Given** a `gate-circular` finding
- **When** `render()` formats the gate output
- **Then** the line carries `[gate-circular]`, not `[proven-awaiting-writer]`
- **Test:** `tests/test_check_pr_acceptance.py::test_gate_circular_render_labels_the_finding_distinctly`

#### Scenario: an ordinary unchecked criterion stays acceptance-unchecked

- **Given** an issue whose unticked criterion does not name the gate's own job
- **When** `make check-pr-acceptance` runs
- **Then** it reports `acceptance-unchecked` (red, blocking) — the classification never swallows a
  real, peer-provable case
- **Test:** `tests/test_check_pr_acceptance.py::test_a_normal_unchecked_criterion_is_STILL_acceptance_unchecked`

#### Scenario: a product use of "guard" is never trapped

- **Given** a criterion "the new quota guard prevents a second overdraw in the model" (a product noun,
  not the CI `guard` job)
- **When** the gate classifies it
- **Then** it stays `acceptance-unchecked`, never `gate-circular`
- **Test:** `tests/test_check_pr_acceptance.py::test_criterion_about_a_product_guard_is_NOT_gate_circular`

#### Scenario: the ## Not covered escape still wins over the classification

- **Given** a gate-circular criterion named out of scope in the PR body under `## Not covered` with a
  linked `#<n>`
- **When** the gate reads the PR body
- **Then** the criterion is not a finding at all
- **Test:** `tests/test_check_pr_acceptance.py::test_gate_circular_yields_to_the_out_of_scope_exemption`

#### Scenario: the live CLI exits zero on a gate-circular close with peers proven

- **Given** a PR closing an issue whose only unticked criterion is gate-circular, other criteria proven
- **When** `check_pr_acceptance.py check --body-file <pr-body>` runs against a live-read issue
- **Then** it exits zero and prints `gate-circular` with `0 violation`
- **Test:** `tests/test_check_pr_acceptance.py::test_cli_gate_circular_close_exits_zero`

### Requirement: the issue shape documents the authoring rule

The repo's issue renderer (`scripts/issue_body.py::_criteria`) MUST state the authoring rule on the
surface that writes `## Acceptance criteria`: a criterion must be PROVABLE by a run or a command it
does not itself gate, so a box of the shape "the PR that fixes it is green in CI on the same job that
failed" is only legitimate when that job is not the acceptance gate's own.

#### Scenario: a documented authoring-rule statement exists

- **Given** the issue renderer's `_criteria` docstring
- **When** a lane reads it to author a criterion
- **Then** it states that a criterion must be provable by a run or command it does not itself gate

