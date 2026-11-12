# Spec Delta: acceptance-body-parity

## ADDED Requirements

### Requirement: A closing PR body's acceptance checklist shall not lag its issue

For every pull request whose body closes `#N`, every unchecked `- [ ]` under the PR body's own
canonical `## Acceptance criteria` section SHALL be reported by `make check-pr-acceptance` as a
blocking finding `acceptance-body-lag` (`where: pr-body`), unless the criterion is named under
the body's `## Not covered` section together with a linked work item. Checkboxes outside the
canonical section are out of scope. A body that restates no criteria SHALL NOT be held.

#### Scenario: closing body with an unticked copy of a ticked criterion

- **Given** an issue `#1000` whose acceptance criteria are all ticked with proven evidence
- **And** a PR body that contains `closes #1000` and its own `## Acceptance criteria` with at
  least one `- [ ]` item
- **When** `acceptance_verdict` evaluates the close
- **Then** the findings include `acceptance-body-lag` with `blocking: true` and `where: pr-body`

#### Scenario: fully ticked body mirror

- **Given** an issue `#1000` with all criteria ticked and proven
- **And** a PR body closing `#1000` whose own `## Acceptance criteria` are all `- [x]`
- **When** `acceptance_verdict` evaluates the close
- **Then** no `acceptance-body-lag` finding is reported

#### Scenario: Not covered exemption

- **Given** a closing PR body with an unticked acceptance item
- **And** the body's `## Not covered` names that criterion and a linked work item
- **When** `acceptance_verdict` evaluates the close
- **Then** no `acceptance-body-lag` finding is reported

#### Scenario: boxes outside the canonical section

- **Given** a closing PR body whose `### Verify` section carries `- [ ]` boxes and whose canonical
  `## Acceptance criteria` section carries none
- **When** `acceptance_verdict` evaluates the close
- **Then** no `acceptance-body-lag` finding is reported
