# ci-discipline — delta for re-homing the deactivated lanes

## ADDED Requirements

### Requirement: Deactivated lanes are classified and declare their live trigger

Every lane whose `schedule:` was removed by the CI-schedule discipline (issue #2701) SHALL be
classified as keep-event-only or retire, and the decision SHALL be recorded in
`scripts/check_ci_discipline.py::DISPATCH_ONLY_LANES` with the driver that triggers the lane
now. Kept lanes SHALL carry a `# Triggered now (issue #2703):` header line in their workflow
file stating the live trigger set and which principals may start it (the owner, a collaborator,
or GitHub itself — the #2718 roster). `check_ci_discipline.py` SHALL fail when a
`DISPATCH_ONLY_LANES` file declares an `on.schedule:` again or has lost the trigger marker line.

#### Scenario: a kept lane without its trigger header is a finding

- **Given** a fixture tree where one dispatch-only lane's workflow lost the `# Triggered now` line
- **When** the discipline check runs on it
- **Then** it exits non-zero naming that workflow file and the missing marker

#### Scenario: a dispatch-only lane that re-schedules itself is a finding

- **Given** a fixture tree where a `DISPATCH_ONLY_LANES` workflow declares `on.schedule:`
- **When** the discipline check runs on it
- **Then** it exits non-zero naming that file

#### Scenario: the live tree classifies all seven lanes

- **Given** the repository tree at this change's head
- **When** `make check-ci-discipline` runs
- **Then** it exits 0 and its `report` mode lists all seven deactivated lanes with their drivers
