# ci-scope-workflow-reporting — spec delta

## ADDED Requirements

### Requirement: The base-ref fallback shall be pinned by behaviour, not spelling

The `scope` job's base-ref resolution SHALL be pinned by a test that **executes** the step body with
the build tools stubbed, asserting the ref handed to `make ci-scope`. A syntax grep of the `run:`
body SHALL NOT be the only pin of the fallback.

#### Scenario: an event that carries no base_ref

- **WHEN** the step body runs with `github.base_ref` evaluating to the empty string (a
  dispatch/schedule-shaped event) and `make`/`git` stubbed to record their argv
- **THEN** the recorded `make` invocation names `BASE=origin/main`

#### Scenario: the fallback announces itself

- **WHEN** that same empty-base_ref run finishes
- **THEN** its stdout names the event and says the diff is reported against main

#### Scenario: a real base_ref needs no fallback

- **WHEN** the step body runs with `github.base_ref` evaluating to a branch name
- **THEN** the recorded `make` invocation names `BASE=origin/<that branch>` and no fallback line
  is printed

### Requirement: The behavioural pin shall fail for the right reasons

Planted variants of the same step body SHALL red the pinned properties: removing the fallback block
SHALL make the recorded ref differ from `origin/main`, and removing the fallback log line SHALL trip
the visibility assertion.

#### Scenario: fallback block removed

- **WHEN** the recorded run uses a body variant whose `if [ -z … ]` block is deleted
- **THEN** the recorded `make` invocation names `BASE=origin/` and the resolution property reports
  a failure

#### Scenario: fallback log line removed

- **WHEN** the recorded run uses a body variant whose `echo` line is deleted
- **THEN** the visibility property reports a failure while the resolution still holds
