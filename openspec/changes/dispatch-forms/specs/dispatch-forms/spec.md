# dispatch-forms

## ADDED Requirements

### Requirement: A dispatchable workflow's name states the work

Every workflow with a `workflow_dispatch` SHALL have a `name:` that states what the run does, not the
file name. A name that repeats the file stem, or that carries no `— what it does` part, or whose
description is shorter than 10 characters SHALL be a violation.

#### Scenario: a name that repeats the file name

- **WHEN** `a-bot.yml` declares `name: a-bot`
- **THEN** the guard SHALL report that the name repeats the file name
- **Test:** `tests/test_dispatch_forms.py::test_a_name_that_repeats_the_file_name_is_a_violation`

#### Scenario: a name without a description

- **WHEN** a file declares `name: PR fix-bot`
- **THEN** the guard SHALL report that the name has no `— what it does` part
- **Test:** `tests/test_dispatch_forms.py::test_a_name_without_a_what_it_does_part_is_a_violation`

### Requirement: The manual dispatch form documents itself

Every input of a `workflow_dispatch` SHALL carry a `description:` of at least 10 characters and either
a `default:` or `required: true`. A bare `workflow_dispatch:` with no `inputs:` SHALL be a violation
unless the file declares `# dispatch: no inputs — <reason>` with a reason of at least 10 characters.

#### Scenario: a bare dispatch form

- **WHEN** a workflow declares `workflow_dispatch:` with no inputs and no reason
- **THEN** the guard SHALL report the bare form
- **Test:** `tests/test_dispatch_forms.py::test_a_bare_workflow_dispatch_is_a_violation`

#### Scenario: a decision, not an oversight

- **GIVEN** a workflow that genuinely takes no input
- **WHEN** it declares `# dispatch: no inputs — <reason ≥ 10 chars>`
- **THEN** the guard SHALL accept it
- **Test:** `tests/test_dispatch_forms.py::test_a_bare_workflow_dispatch_with_a_real_reason_is_allowed`

#### Scenario: an input whose empty meaning is undefined

- **WHEN** an input has neither `default:` nor `required: true`
- **THEN** the guard SHALL report it
- **Test:** `tests/test_dispatch_forms.py::test_an_input_with_neither_default_nor_required_is_a_violation`

### Requirement: The header block states the contract

Every dispatchable workflow SHALL carry `# Trigger surface:`, `# Flow:` and `# Never:` in its header,
where `Flow` names the make target behind each stage and `Never` states the invariants the workflow
must not break.

#### Scenario: a missing key

- **WHEN** a dispatchable workflow's header omits `# Never:`
- **THEN** the guard SHALL report the missing key
- **Test:** `tests/test_dispatch_forms.py::test_a_missing_header_key_is_a_violation`

### Requirement: The README's dispatch table is generated, not written

The README SHALL carry the dispatch table between the `dispatch-forms` markers, generated from the
workflow files by `make dispatch-forms-report`. The guard SHALL fail when the table no longer matches
the workflows, and SHALL report a missing marker block.

#### Scenario: a stale table

- **WHEN** a workflow's inputs change and the table is not regenerated
- **THEN** the guard SHALL fail and name the command that regenerates it
- **Test:** `tests/test_dispatch_forms.py::test_a_stale_readme_table_fails_and_a_fresh_one_passes`

### Requirement: The guard gates CI and this repository passes it

`make check-dispatch-forms` SHALL run inside the `ci-unit` job and SHALL exit non-zero on any
violation. Every bot workflow in this repository SHALL be dispatchable, named for its work, and either
documented inputs or an explicit reason for none.

#### Scenario: the exit code is what CI gates on

- **WHEN** the guard finds a violation
- **THEN** `main(["check"])` SHALL return non-zero, and 0 on a clean tree
- **Test:** `tests/test_dispatch_forms.py::test_check_exits_non_zero_on_a_violation_and_zero_on_a_clean_tree`

#### Scenario: this repository states what every dispatchable run does

- **WHEN** the guard runs over this repository
- **THEN** it SHALL report no violation and a matching README table
- **Test:** `tests/test_dispatch_forms.py::test_this_repository_states_what_every_dispatchable_run_does`

### Requirement: A documented input reaches the code it promises

An input the dispatch form offers SHALL be wired to a real code path — a `dry` input that nothing
reads is worse than no input, because the form then lies. `engine-bump-rebase`'s `dry` SHALL reach the
script's `--dry` through `make engine-bump-rebase DRY=1`, and its step SHALL call the make target
rather than the script directly.

#### Scenario: the dry input is real

- **WHEN** `engine-bump-rebase.yml` is read
- **THEN** its run block SHALL call `make engine-bump-rebase`, pass `inputs.dry`, and the make target
  SHALL run `scripts/engine_bump_rebase.py`
- **Test:** `tests/test_engine_bump_rebase.py::TestWorkflowYaml::test_workflow_runs_the_rebase_entrypoint`
