# Umbrella open-lane close gate

## ADDED Requirements

### Requirement: the acceptance gate holds a close while a referenced rollout lane is open

The merge-time acceptance gate (`scripts/check_pr_acceptance.py`) enumerates the rollout lanes a
linked umbrella references and holds the PR's close while any referenced lane issue is still OPEN,
independent of the umbrella's own `- [ ]` criteria ticks. A lane is a referenced issue whose own
body cites the umbrella back (the bidirectional signal measured on #1849's fleet: every lane
carries `#1849`; incidental process refs `#1791`/`#1792`/`#1724`/`#791` never do). Referenced-open
issues that do NOT cite the umbrella back are process context and must not hold the close, so a
legitimate final-lane merge with an unrelated open referenced issue stays green.

#### Scenario: a close fires on a fully-ticked umbrella with an open lane

Given a PR whose body (or squash text) closes an umbrella whose `## Acceptance criteria` are all
ticked
And a referenced issue that is still OPEN and whose own body carries `#<umbrella>`
When the acceptance gate runs with the linked issue read live
Then the gate is RED with a `rollout-lane-open` finding naming the open lane
And the merge is held, so the umbrella does not auto-close.

#### Scenario: a referenced-open issue that does not cite the umbrella is not a lane

Given a PR whose body closes an umbrella
And a referenced issue that is still OPEN but whose own body does NOT carry the umbrella's number
When the acceptance gate runs with the linked issue read live
Then the close is NOT held for that reference
And the gate verdict depends only on the umbrella's own criteria and any true lanes.

#### Scenario: all referenced lanes closed, close allowed

Given a PR whose body closes an umbrella whose referenced lane issues are all CLOSED
When the acceptance gate runs with the linked issue read live
Then there is no `rollout-lane-open` finding
And the close proceeds subject only to the umbrella's own criteria.

### Requirement: the lane set is derived, never a hand-kept list

The gate derives the candidate lane set from the umbrella's live body at merge time (a
`#<umbrella>` reverse-citation probe), never from a hardcoded roster of issue numbers, so a new
lane added to an existing umbrella is held automatically without editing the gate.

#### Scenario: a newly-added lane is held without gate changes

Given a rollout umbrella whose body references a newly-created lane issue that is OPEN
And that lane issue's body carries the umbrella's number back
When the acceptance gate runs
Then the new lane is held as `rollout-lane-open` without any change to the gate's code.
