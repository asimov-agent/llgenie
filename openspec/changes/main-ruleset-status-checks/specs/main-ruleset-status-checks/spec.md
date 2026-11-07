# Main ruleset status-checks guard

## ADDED Requirements

### Requirement: The guard measures the main ruleset's required status checks and fails when they are missing or under-pinned

`check_main_ruleset.py` reads the live `main` ruleset (by default `repos/<owner>/<repo>/rulesets`,
resolved to the one on the default branch; `--ruleset-id` overrides) and exits non-zero when no
`required_status_checks` rule is present, or when the present rule's `parameters.contexts` is not a
**superset** of the pinned context floor (each pinned context must be listed). An extra listed context,
or a reordering, is not a finding: the pin is an additive floor, so a legitimate addition to the
pipeline never reds the guard. A ruleset that fails every read (the token cannot read rulesets, the
API returns an error) exits 2 with the error named — a read failure is never reported as a clean pass
(no BY-PASS on unreadable state). `--fixture ruleset.json` runs the same logic offline against a file,
so the tests prove the guard catches the bug without touching the live API.

#### Scenario: a ruleset with no required_status_checks is a red finding

Given a ruleset whose `.rules` are exactly `[{type: deletion}, {type: non_fast_forward}]` (the live
`main` ruleset id 24862727 as measured 2026-11-07, fixture `tests/fixtures/main-ruleset-gap.json`),
when `check_main_ruleset.py check --fixture` runs,
then it exits non-zero and names the missing `required_status_checks` rule.

- **Test:** `tests/test_check_main_ruleset.py::test_check_subprocess_exits_1_for_the_gap_and_0_for_the_covered_state` and `::test_missing_rule_is_red` and `::test_report_exits_zero_on_a_red_finding`

#### Scenario: a ruleset that lists every pinned context is green

Given a ruleset whose `.rules` include a `required_status_checks` rule listing every context in the
pinned floor set (fixture `tests/fixtures/main-ruleset-covered.json` = the scripted apply's outcome),
when `check_main_ruleset.py check --fixture` runs,
then it exits 0.

- **Test:** `tests/test_check_main_ruleset.py::test_covered_ruleset_is_green`

#### Scenario: a ruleset that lists only some pinned contexts names the missing ones

Given a ruleset whose `required_status_checks.parameters.contexts` is a proper subset of the pinned
floor (e.g. the `ci-verdict` context is absent, fixture `tests/fixtures/main-ruleset-partial.json`),
when `check_main_ruleset.py check --fixture` runs,
then it exits non-zero and names each missing context.

- **Test:** `tests/test_check_main_ruleset.py::test_partial_rule_names_each_missing_context`

#### Scenario: the pin is additive, not exact

Given a ruleset whose `required_status_checks.parameters.contexts` lists every pinned context plus one
new context the pipeline added,
when `check_main_ruleset.py check --fixture` runs,
then it exits 0 (an extra listed context is not a finding).

- **Test:** `tests/test_check_main_ruleset.py::test_pin_is_additive_not_exact`

#### Scenario: an unreadable ruleset is UNKNOWN, never clean

Given an API read that fails (the token cannot read rulesets, or the endpoint errors),
when `check_main_ruleset.py check` runs,
then it exits 2 and prints the read error.

- **Test:** CI behaviour, not a hermetic unit (the live read exercised by `main-ruleset.yml`); the exit-2
  path is the `RuntimeError` handler in `scripts/check_main_ruleset.py::main`

### Requirement: The guard reports what it measures

`check_main_ruleset.py report` prints the ruleset id, enforcement, the present rule types, the
required-status-checks contexts found, and the pinned floor — and exits 0 regardless of the finding, so
a bad state can still be read by a human or a called workflow.

#### Scenario: report exits zero even on a red finding

Given the two-rule ruleset of the red scenario,
when `check_main_ruleset.py report --fixture` runs,
then it exits 0 and its output names the state it measured.

- **Test:** `tests/test_check_main_ruleset.py::test_report_exits_zero_on_a_red_finding`

### Requirement: The scripted ruleset update is add-only and owner-run

`check_main_ruleset.py apply` builds the PUT body for the target ruleset that APPENDS
`required_status_checks` (parameters.contexts = the pinned floor) to the existing non-destructive rules
(`deletion`, `non_fast_forward`) and keeps enforcement/conditions unchanged. It is DRY by default: it
prints the body and does not send it. `apply --apply` sends the PUT with the ambient `gh` token and
reports the HTTP result. The mutation itself is owner-admin-only (a non-admin token receives 404 on
PUT, measured), so the command's default must be DRY and the help line must say an admin token is
required to perform it.

#### Scenario: apply prints the payload and sends nothing by default

Given a ruleset with only `deletion` and `non_fast_forward`,
when `check_main_ruleset.py apply --ruleset-id 24862727` runs (no `--apply`),
then it prints a JSON body whose `.rules` include `required_status_checks` with the pinned contexts and
makes no PUT call.

- **Test:** `tests/test_check_main_ruleset.py::test_apply_cli_defaults_to_dry_and_prints_add_only_body` and `::test_apply_body_is_add_only`

### Requirement: The guard has a consumer

A scheduled monitor workflow (`main-ruleset.yml`) runs `make check-main-ruleset` on its own cron
minute (issue #275: a minute no other bot owns) plus `workflow_dispatch`, so a missing/under-pinned
ruleset is a visible red run a lane and the owner can see — never a definition nobody runs. It never
runs in a pull request (a per-PR run would red every PR while the platform rule is absent) and never
mutates anything; its red completion is routed by `run-failure-reactor` (the workflow's name is in that
workflow's `workflow_run.workflows` roster, so a real failure has a consumer).

#### Scenario: the missing rule is alarmed, not hidden

Given the monitor workflow triggered on its schedule while the live `main` ruleset lacks
`required_status_checks`,
when the `make check-main-ruleset` step runs,
then it exits non-zero and the workflow run is red, naming the gap, and the run-failure-reactor files
or updates a deduped issue for it.

- **Test:** CI behaviour of `main-ruleset.yml`; the exit-1 red contract is locked by
  `tests/test_check_main_ruleset.py::test_check_subprocess_exits_1_for_the_gap_and_0_for_the_covered_state`
