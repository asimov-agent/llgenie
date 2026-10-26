# issue-bot-gates

## ADDED Requirements

### Requirement: the issue-bot re-checks the fast gates before it pushes

`make issue-bot-gates` MUST run the fast repository gates in order and stop at the FIRST failure,
printing each gate as it starts and naming the one that failed. The gates are `lint`,
`check-workflows`, `check-wiring`, `check-docs`, `check-pr-hygiene` and `openspec-tasks-check`, in
that order. It MUST NOT run `test-unit` — the implement leg's agent already ran the suite, and a
second 11–20 minute run does not fit the leg's budget.

WHEN the issue-bot is about to push a change and a fast gate is red
THEN the run fails before the push, naming the gate, so no red branch reaches a reviewer and no
`fix-bot` cycle is spent on it.

#### Scenario: a red gate stops the run and the gates after it never start

- **Given** a checkout whose second fast gate fails and whose third writes a marker file
- **When** the gate runner runs those three gates in order
- **Then** it exits non-zero, prints each gate it started, names the failing gate as `make <gate>`
- **And** it never starts the third gate (its marker file is absent)
- **Test:** `tests/test_issue_bot_gates.py::test_run_stops_at_the_first_failing_gate_and_names_it`

#### Scenario: the gate list is the six the issue names, in its order

- **Given** the guard module
- **When** its fast gates are read
- **Then** they are exactly `lint`, `check-workflows`, `check-wiring`, `check-docs`,
  `check-pr-hygiene`, `openspec-tasks-check` in that order
- **Test:** `tests/test_issue_bot_gates.py::test_the_fast_gates_are_exactly_the_six_the_issue_names`

#### Scenario: the make target really runs the gate runner

- **Given** the real Makefile
- **When** `make -n issue-bot-gates` is asked what the target would do
- **Then** the target is declared `.PHONY` and its recipe runs `scripts/issue_bot_gates.py run`
- **Test:** `tests/test_issue_bot_gates.py::test_the_target_runs_the_gate_script`

### Requirement: the gate runs between the change detection and the push

`.github/workflows/issue-bot.yml` MUST run `make issue-bot-gates` in exactly one step that follows
`Detect what the implementation changed` and precedes `Commit + push the feature branch`, and that
step MUST require a changed tree (`steps.diff.outputs.changed == 'true'`) and the `implement`
verdict. A guard placed after the push, or before the tree is known to have changed, buys nothing.

WHEN the issue-bot workflow is read
THEN the gate step is exactly one step, conditioned on a change, and strictly between the detection
and the push.

#### Scenario: a step moved after the push is a finding

- **Given** a checkout whose issue-bot workflow runs the gate step after the push step
- **When** the static check runs
- **Then** it fails, naming the ordering violation and the push step the gate must precede
- **Test:** `tests/test_issue_bot_gates.py::test_a_step_moved_after_the_push_reds_the_check`

#### Scenario: the real workflow places the gate correctly

- **Given** the real `.github/workflows/issue-bot.yml`
- **When** its implement job's steps are read in order
- **Then** one step runs `make issue-bot-gates`, it is after the change detection and before the
  push, and it carries the `changed == 'true'` condition
- **Test:** `tests/test_issue_bot_gates.py::test_the_issue_bot_runs_the_gate_between_detection_and_push`

#### Scenario: a gate with no test image prepared for it is a finding

`make lint` runs inside `llgenie/test` (the same path `ci-lint` uses). A fresh runner has no such
tag, so a gate with no earlier `make test-image`/`make test-env` fails on the runtime before it
checks anything.

- **Given** a checkout whose gate step has no `make test-image` or `make test-env` before it
- **When** the static check runs
- **Then** it fails, naming the missing environment preparation
- **Test:** `tests/test_issue_bot_gates.py::test_a_gate_that_never_prepares_the_test_image_reds_the_check`

### Requirement: a gate the pipeline runs is classified, and the classification cannot rot

Every gate `make ci-unit` runs MUST be either in `FAST_GATES` (re-checked before the push) or in
`DEFERRED` with the reason it is not. A gate in **neither** MUST be an error naming the gate and
both ways to classify it. A `DEFERRED` entry that `ci-unit` no longer runs, or that contradicts
`FAST_GATES`, MUST be an error. A fast gate that is not a make target, is not declared `.PHONY`, or
that no `ci-*` job reaches MUST be an error. `make issue-bot-gates-check` (and
`tests/test_issue_bot_gates.py` under `make test-unit`) enforce all of it, so a new fast gate
cannot be silently skipped before the push.

WHEN a gate is added to `ci-unit`
THEN `make test-unit` fails until the gate is classified as fast (and so re-checked by the bot) or
deferred (with its reason).

#### Scenario: an unclassified ci-unit gate reds the check

- **Given** a checkout whose `ci-unit` recipe runs one more gate than the guard classifies
- **When** the static check runs
- **Then** it fails, naming the gate and both ways to classify it (`FAST_GATES` / `DEFERRED`)
- **Test:** `tests/test_issue_bot_gates.py::test_a_new_ci_unit_gate_nobody_classified_reds_the_check`

#### Scenario: a stale classification is named

- **Given** a checkout whose `ci-unit` no longer runs a gate `DEFERRED` records
- **When** the static check runs
- **Then** it fails, naming the stale entry
- **Test:** `tests/test_issue_bot_gates.py::test_a_stale_deferred_entry_is_named`

#### Scenario: the real tree is wired

- **Given** the real checkout
- **When** the static check runs
- **Then** it reports no finding
- **Test:** `tests/test_issue_bot_gates.py::test_the_real_tree_is_wired`

### Requirement: the gate is wired into the pipeline it protects

`ci-unit` MUST run `make issue-bot-gates` and `make issue-bot-gates-check` (both plain host-side
targets, seconds each), and the runner MUST be reached from a make target, so neither the gate nor
its own check can become dead code.

WHEN the Makefile is read
THEN `ci-unit` calls both targets and `make issue-bot-gates-check` exits 0 on the real tree
(otherwise `check-wiring` and `check-docs` fail the same job).

#### Scenario: a target `ci-unit` stopped calling is a finding

- **Given** a checkout whose `ci-unit` recipe no longer calls `make issue-bot-gates` (or
  `make issue-bot-gates-check`)
- **When** the static check runs
- **Then** it fails, naming the target the pipeline no longer reaches
- **Test:** `tests/test_issue_bot_gates.py::test_a_runner_ci_unit_stopped_calling_is_a_finding`
