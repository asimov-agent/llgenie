# guard-write-level-arm

## ADDED Requirements

### Requirement: the write-level rule derives the accepted set from the guard's `case` arm

The rule that a trigger guard accepts a write level and nothing weaker MUST read the SET the guard's own
`case` arm accepts, not whether the three allowed words appear somewhere in the step text. A guard whose
arm also accepts `read`/`triage` (or any weaker level, or a bare `*`) MUST be a test failure naming the
workflow. An arm that `exit`s is the refusal arm and MUST NOT contribute to the accepted set.

WHEN a guard's `case` arm accepts a level weaker than `write`, or accepts everything
THEN `make test-unit` fails, naming the workflow and the set it actually accepts.

#### Scenario: an arm that also accepts read is a failure

- **Given** a guard whose `case` arm is `admin|maintain|write|read`
- **When** the write-level rule reads the accepted set
- **Then** the set is not `{admin, maintain, write}` and the guard is reported, naming the workflow
- **And** the substring check this replaced (`all(level in text for level in ALLOWED)`) accepts the SAME
  arm, which is why the rule had to change
- **Test:** `tests/test_workflow_guards.py::test_the_write_level_rule_reads_the_decision_not_the_prose`
  and `tests/test_workflow_guards.py::test_the_guard_checks_both_actors_and_a_write_level`

#### Scenario: the eleven committed guards read as exactly write-level

- **Given** the committed `.github/workflows/*.yml`
- **When** the rule reads each guard's `case` arm
- **Then** every guard accepts exactly `{admin, maintain, write}`
- **And** each guard's file mentions `github.triggering_actor`
- **Test:** `tests/test_workflow_guards.py::test_the_guard_checks_both_actors_and_a_write_level`

#### Scenario: an arm that accepts only read, or everything, is a failure

- **Given** a guard whose `case` arm is `read`, `triage`, or `*`
- **When** the write-level rule reads the accepted set
- **Then** the set is not `{admin, maintain, write}` in every case
- **Test:** `tests/test_workflow_guards.py::test_the_write_level_rule_reads_the_decision_not_the_prose`

### Requirement: the `204` check reads the guard body, not the whole job

The negative check for the older `curl`-`204` guard form MUST read the run text of the guard step itself,
never the joined run text of every step in its job, so an unrelated step that merely mentions `204`
cannot trip it. `read`/`triage` MUST NOT be accepted as a permission level by any guard.

WHEN a job contains a guard step and another step that mentions `204`
THEN the `204` rule does not fire, because it reads the guard step only.

#### Scenario: the guard's own script is what the 204 rule reads

- **Given** a workflow whose guard step uses `gh api …/permission` and whose guard text contains no `204`
- **When** the write-level rule collects the guard body
- **Then** it reads only the guard step's `run` text (`_guard_runs`), and the `204` check does not fire
- **Test:** `tests/test_workflow_guards.py::test_the_guard_checks_both_actors_and_a_write_level`
