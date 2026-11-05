# status-keeper-acceptance-form-contract

## ADDED Requirements

### Requirement: the status-keeper lane's skill carries the acceptance-criteria form contract
The `llgenie-status-keeper` lane's versioned skill MUST state, verbatim per #1796 #1, that every
issue this lane files AND every PR body it opens carries a `## Acceptance criteria` section whose
items are each a `- [ ]` markdown checkbox — one per provable outcome; a criterion a reviewer
cannot tick is not one (#745). The changed skill is text-only under `agents/llgenie-status-keeper/`
and versioned via #791 with the #1724 SYNC line.

WHEN the status-keeper lane files an issue or opens a PR body,
THEN the body carries a `## Acceptance criteria` section with at least one `- [ ]` checkbox per
provable outcome.

#### Scenario: an issue the status-keeper files carries tickable acceptance criteria
- **Given** the status-keeper lane files an issue (any path)
- **Then** the body contains `## Acceptance criteria` with each criterion as a `- [ ]` checkbox,
  one per provable outcome

#### Scenario: a PR the status-keeper opens carries tickable acceptance criteria
- **Given** the status-keeper lane opens a PR body
- **Then** the body contains `## Acceptance criteria` with each criterion as a `- [ ]` checkbox,
  one per provable outcome

#### Scenario: a non-tickable criterion is not the form
- **Given** a criterion a reviewer cannot tick
- **Then** it is not a valid acceptance criterion (#745)

### Requirement: the change is text-only under the lane's own agents dir
The versioned SKILL.md change MUST be text-only under `agents/llgenie-status-keeper/`, with the
#1724 SYNC line; no edit to `issue_body.py`, `acceptance_writeback`, or `auto-merge.yml`
(#1644/#1088/#491 intact).

WHEN the status-keeper lane versioned its contract via #791,
THEN the diff touches only `agents/llgenie-status-keeper/` and the change-note machinery.

#### Scenario: the versioned change touches only the lane's own dir
- **Given** the status-keeper lane versions its acceptance-criteria contract via #791
- **When** the PR diff is inspected
- **Then** every lane-owned path is under `agents/llgenie-status-keeper/`
- **And** no `issue_body.py`, `acceptance_writeback`, or `auto-merge.yml` file is edited
  (#1644/#1088/#491 intact)
