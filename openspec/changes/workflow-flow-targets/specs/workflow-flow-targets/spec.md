# workflow-flow-targets

## ADDED Requirements

### Requirement: a `Flow:` stage names a make target that exists

Every `make <target>` in a **stage position** on a dispatchable workflow's `Flow:` header line — or on
one of its continuation lines — SHALL be a target the `Makefile` defines. A stage position is right
after `->`, or at the start of the `Flow:` line or a continuation line. `make check-dispatch-forms`
(the `ci-unit` gate) SHALL fail otherwise, because the header is what a maintainer reads to learn the
pipeline, and a stage no one can run misdescribes it.

#### Scenario: a stage no one can run is a violation

- **GIVEN** a workflow whose `Flow:` line names `make ghost-target` and a `Makefile` that does not
  define `ghost-target`,
- **WHEN** the guard reads it,
- **THEN** it reports that the header's `Flow:` names a target that is not in the `Makefile`.

- **Test:** `tests/test_dispatch_forms.py::test_a_flow_naming_a_target_that_does_not_exist_is_a_violation`

#### Scenario: a continuation line is scanned too

- **GIVEN** a `Flow:` line wrapped over several comment lines, with the bad stage on the second one,
- **WHEN** the guard reads it,
- **THEN** the continuation is scanned and the violation is reported.

- **Test:** `tests/test_dispatch_forms.py::test_a_continuation_of_the_flow_line_is_scanned`

#### Scenario: every stage being a real target passes

- **GIVEN** a workflow whose every `Flow:` stage is a target the `Makefile` defines,
- **WHEN** the guard reads it,
- **THEN** it reports nothing.

- **Test:** `tests/test_dispatch_forms.py::test_a_flow_naming_only_real_targets_passes`

### Requirement: the rule must not fire on prose or on a placeholder

The `Flow:` line is prose, so an unanchored `make <word>` match would fire on ordinary English
(`that decision lives in a make target`). The rule SHALL count only stage positions, and SHALL skip a
placeholder (`make ci-<job>`).

#### Scenario: prose mentioning a make target is not a finding

- **GIVEN** a `Flow:` line that says a stage is "not in a make target" in prose,
- **WHEN** the guard reads it,
- **THEN** there is no violation.

- **Test:** `tests/test_dispatch_forms.py::test_prose_that_merely_says_make_target_is_not_a_violation`

#### Scenario: a placeholder stage is skipped

- **GIVEN** a `Flow:` line naming `make ci-<job>`,
- **WHEN** the guard reads it,
- **THEN** there is no violation.

- **Test:** `tests/test_dispatch_forms.py::test_a_placeholder_stage_is_not_a_violation`

### Requirement: this repository's flows name only real targets

Every `Flow:` stage in this repository's workflows SHALL resolve to a `Makefile` target.

#### Scenario: the repository is clean

- **GIVEN** the repository's workflows and `Makefile`,
- **WHEN** the guard runs,
- **THEN** no header names a target that does not exist.

- **Test:** `tests/test_dispatch_forms.py::test_the_repository_flows_name_only_real_targets`

### Requirement: the documented publish flow matches the workflow

`publish-agent-image.yml`'s `Flow:` SHALL describe the stages the job actually runs, and `README.md`
SHALL describe the publish as implemented (including that the push pre-flight is not implemented and
is tracked by its own issue).

#### Scenario: the header names the real stages

- **GIVEN** `publish-agent-image.yml`,
- **WHEN** its `Flow:` line is read,
- **THEN** it names `make publish-agent-image` and `make ci-image-refs`, and names no target the
  `Makefile` does not define.

- **Test:** `tests/test_dispatch_forms.py::test_the_repository_flows_name_only_real_targets` (the
  repository-wide form of the assertion)
