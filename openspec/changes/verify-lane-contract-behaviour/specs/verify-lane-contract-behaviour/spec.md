# Verify the lane behavioural contract

## ADDED Requirements

### Requirement: `verify_lane_contract.py` asserts behaviour, not file drift

`scripts/verify_lane_contract.py` checks every live llgenie lane's SOUL under
`$HOME/.hermes/profiles/<lane>/` (built from `pathlib.Path.home()`, never the
tree and never a hardcoded account path) against six contract elements —
`report-line`, `never-merge`, `bookend`, `no-private-edit`, the lane's own
`own-duty` (one regex per lane in the `DUTY` map), and `communicate` — plus a
`skills-materialised` axis (≥1 non-`.archive` `SKILL.md` under `skills/`). A FAIL
names the lane and the specific missing element.

#### Scenario: a clean live lane passes

Given a lane's live SOUL carries the report line, never-merge, bookend,
issue+PR-under-`agents/<profile>/`, its own duty marker, a communication
commitment, and a materialised skill
When the checker is run against that lane
Then it reports `N lanes pass the behavioural contract` with that lane counted
And the exit code is 0

#### Scenario: an empty SOUL fails

Given a lane whose live SOUL.md is empty
When the checker is run
Then the lane is a FAIL
And the exit code is 1

#### Scenario: a missing report line fails

Given a lane whose SOUL has every contract element but no `working on #` report line
When the checker is run
Then the lane is a FAIL naming `report-line`
And the exit code is 1

#### Scenario: no communication commitment fails

Given a lane whose SOUL names no `message_agent` / report-to / recall / shared bank
When the checker is run
Then the lane FAILs the `communicate` axis
And the exit code is 1

#### Scenario: removing a lane's own-duty marker reds it

Given a lane whose SOUL otherwise passes
When its own-duty marker is removed (and the SOUL's remaining text is unchanged)
Then that lane FAILs `own-duty`
And the exit code is 1

#### Scenario: archived-only skills fail the materialised axis

Given a lane whose `skills/` holds only `.archive` stubs (no non-archived `SKILL.md`)
When the checker is run
Then the lane FAILs `skills-materialised`
And the exit code is 1

### Requirement: the gate builds its path from `pathlib.Path.home()`

The checker never hardcodes a machine account path; the default profiles root is
`pathlib.Path.home() / ".hermes" / "profiles"`, overridable with `--root` so a
hermetic test can point at a scratch fixture. A SOUL read is the LIVE setup, never
the tree.

#### Scenario: default root is `$HOME/.hermes/profiles`

Given `--root` is not passed
When the checker runs
Then it reads `$HOME/.hermes/profiles/llgenie-*/SOUL.md`

#### Scenario: a scratch fixture is verifiable

Given a test passes `--root <tmp>` with a scratch lane constructed there
When the checker runs
Then it verifies exactly that fixture and touches no live profile

### Requirement: a regression is the planner's fix, never the lane's self-patch

The orchestrator tick step 9 (VERIFY LANE RESPONSIBILITY) runs the checker after
dispatch and quotes the pass-count. On a FAIL the planner does NOT tell the lane
to fix its own SOUL; it files a detailed issue under `agents/<lane>/` and the
lane lands the SOUL correction by PR under `agents/<profile>/`.

#### Scenario: tick step 9 runs the checker and quotes the count

Given the versioned orchestrator procedure
When step 9 executes
Then it runs `scripts/verify_lane_contract.py` and quotes `N/13 lanes pass the
behavioural contract` plus any FAIL line as evidence

#### Scenario: the planner owns the regression

Given a lane FAILs the behavioural contract
When the planner handles it
Then it files a detailed issue under `agents/<lane>/` rather than instructing the
lane to edit its own SOUL
