## ADDED Requirements

### Requirement: Commit text carries the ticked acceptance mirror

The joined commit messages of a bot PR range (`origin/main..HEAD`, `--no-merges`) SHALL carry the
PR body's acceptance criteria as ticked checkboxes, and SHALL NOT carry an unchecked `- [ ]`
under an acceptance heading. The gate is `make check-pr-commit-checkboxes`
(`scripts/check_pr_hygiene.py commit-checkboxes`).

#### Scenario: Squash text with an unticked acceptance box is refused

- **Given** a bot PR whose commit message embeds an `## Acceptance criteria` section with `- [ ]` items (the measured #2509 shape in `49f0cc3be`)
- **When** `make check-pr-commit-checkboxes` runs on the range
- **Then** it exits 1 naming the `commit-unchecked-acceptance` finding and the offending count

#### Scenario: A ticked mirror satisfies the gate

- **Given** a bot PR body whose `## Acceptance criteria` declares N ticked `- [x]` items and whose commits carry at least N `- [x]` boxes with none unchecked
- **When** `make check-pr-commit-checkboxes` runs on the range
- **Then** it exits 0

#### Scenario: Declared criteria without a commit mirror are refused

- **Given** a bot PR body declaring N acceptance items while its commit text carries fewer than N `- [x]` boxes
- **When** `make check-pr-commit-checkboxes` runs on the range
- **Then** it exits 1 naming the `commit-acceptance-unmirrored` finding

#### Scenario: Human-only ranges are skipped

- **Given** a PR range with no bot-authored commit
- **When** the gate runs on it
- **Then** it exits 0 (the mandate is stated for fleet lanes, mirroring `is_bot_pr`)

### Requirement: The merge lane never lands unchecked acceptance text

`scripts/auto_merge.py::_merge` SHALL re-read the PR's live commit messages and live PR body
before the `gh pr merge` call and SHALL defer (reason on the PR via the existing per-head deferral
comment, exit 0) when the same `commit-checkboxes` findings apply. It SHALL NOT red the run and
SHALL NOT merge.

#### Scenario: Unticked commit checkboxes defer the merge

- **Given** a green, CLEAN, review-cleared PR whose commit messages still contain an unticked acceptance box
- **When** the auto-merge lane reaches it
- **Then** the PR is NOT merged, a deferral comment naming issue #2519 is posted at the head sha, and the job exits 0

#### Scenario: Closing stays the one automatic act

- **Given** a PR whose commit text, PR body and issue body all carry the same ticked acceptance set
- **When** the merge lands and the body's `closes #N` keyword fires
- **Then** GitHub closes the issue exactly once and no gate, script, or agent closes or ticks it by hand

### Requirement: The gate is wired where the fleet runs it

`make check-pr-commit-checkboxes` SHALL be a Makefile target in `mk/gates.mk`, classified in
`scripts/issue_bot_gates.py::DEFERRED` with a reason (the `FAST_GATES` roster is the fixed #475
list, mirroring `check-pr-closing`), and run as a live-body step in the `ci.yml` guard job beside
`check-pr-agents-line`.

#### Scenario: The guard job refuses an unmirrored PR before any merge

- **Given** a PR whose commit text carries no `- [x]` acceptance mirror for its body's declared criteria
- **When** the `ci.yml` guard job runs `make check-pr-commit-checkboxes` with the live PR body
- **Then** the guard job (a required job) fails at that step and the PR is never armed
