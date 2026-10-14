# issue-refiner

## ADDED Requirements

### Requirement: The refiner never races the implementer

`pick` SHALL refuse to select an issue while an issue is waiting for the implementer — labelled
`agent:implement` or `agent:ready` and not yet implemented (no pull request links it) — reporting
the reason. It SHALL run hourly and review ONE issue per run, and SHALL NOT block on work the
implementer has already started.

#### Scenario: an issue is waiting for the implementer

- **GIVEN** an issue labelled `agent:implement` with no pull request
- **WHEN** `pick` runs
- **THEN** it SHALL return no issue and say it is yielding to the implementer

#### Scenario: a labelled issue that already has a PR does not block

- **GIVEN** the only labelled issue already has a pull request
- **WHEN** `pick` runs
- **THEN** it SHALL proceed to select the oldest eligible issue

### Requirement: Only a not-yet-implemented, undecided issue is picked

`pick` SHALL choose the oldest open issue that is not labelled `agent:refined`, `agent:closed`,
`agent:implement` or `agent:ready`, and that GitHub does not report as linked to a pull request.

#### Scenario: decided, claimed and already-implemented issues are skipped

- **GIVEN** four issues: one refined, one claimed for implementation, one linked to a PR, and one clean
- **WHEN** `pick` selects
- **THEN** it SHALL select the clean one

### Requirement: The review is one comment and a label, never a PR

`apply` SHALL post exactly ONE comment carrying the `RESTATED:` restatement (for `refined`) or the
reason (for `already-clear`) and add the `agent:refined` label. It SHALL NOT create a branch, open a
pull request, or edit the issue body. A `refined` verdict with no `RESTATED:` block, and any
unrecognised or missing verdict, SHALL exit non-zero having mutated nothing.

#### Scenario: a refinement lands as a comment

- **WHEN** the verdict is `refined` with a restatement
- **THEN** one comment SHALL be posted and `agent:refined` added
- **AND** no pull request SHALL be created

#### Scenario: an empty refinement is refused

- **WHEN** the verdict is `refined` without a `RESTATED:` block
- **THEN** the command SHALL exit non-zero and change nothing
