# Spec delta: planner-merge-behavior (issue #3084)

## ADDED Requirements

### Requirement: the planner SOUL MUST describe CI-only landing

`agents/llgenie-planner/SOUL.md` MUST NOT say that every merge needs the owner's approval or
tell the planner to stop at a reviewable PR as a wait state. It MUST state that the planner
never hand-merges and never pushes to `main`, and that CI's `auto-merge` job in
`.github/workflows/ci.yml` squash-merges a PR when every relevant PR job passed and
`mergeStateStatus == CLEAN`, with no human click, per `AGENTS.md` rule 7.

An approval MUST be described as neither a precondition for landing nor a licence to merge;
`REVIEW_REQUIRED` MUST be described as not a human gate to wait on.

#### Scenario: a green CLEAN PR lands without a human click

- **Given** a PR whose relevant CI jobs all passed and whose `mergeStateStatus` is `CLEAN`
- **When** the planner reads its own SOUL's merge paragraph
- **Then** the paragraph says CI squashes the PR itself with no human click, and does not
  require the planner to wait for an owner's approval

#### Scenario: the stale approval gate is gone

- **Given** the live `agents/llgenie-planner/SOUL.md` at the change's head
- **When** the text is searched for the old clause about the owner's approval
- **Then** no such clause is present, and `REVIEW_REQUIRED` is named as not a human gate

### Requirement: an in-flight CI run MUST NOT idle the planner

While one PR's CI is in flight, the planner SOUL MUST direct the planner to take the next
un-PR'd board issue end-to-end (issue, OpenSpec change, worktree, gates, PR), one lane at a
time, instead of idling or polling that run.

#### Scenario: CI is still running on a pushed PR

- **Given** a pushed PR with a CI run still in progress
- **When** the planner chooses its next action
- **Then** its governing text says to pick up the next un-PR'd board issue rather than wait
  on the run
