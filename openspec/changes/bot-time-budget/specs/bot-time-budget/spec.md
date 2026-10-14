# bot-time-budget

## ADDED Requirements

### Requirement: A bot job's budget fits the work it may do

A job that runs the agent SHALL allow at least 60 minutes, and the fix-bot's job SHALL allow at
least `FIX_ROUNDS x (check + repair)` as measured for the repo's own check, so a long repair is
never killed mid-round.

#### Scenario: the fix job fits its rounds

- **GIVEN** `scripts/fix_loop.sh` defaults to 3 rounds
- **WHEN** the workflow budgets are read
- **THEN** the fix job SHALL allow at least 3 x (20 min check + 30 min repair)

#### Scenario: a step cannot undercut the job

- **GIVEN** a bot job's steps
- **WHEN** any step declares `timeout-minutes`
- **THEN** it SHALL be at least 60 minutes

### Requirement: Nothing outside the job caps a round, and the short jobs stay short

`scripts/fix_loop.sh` SHALL NOT wrap a round in `timeout`, and the decision-only jobs (guard,
sweep) SHALL keep a budget of at most 30 minutes so they fail fast rather than hang.

#### Scenario: no hidden per-round cap

- **WHEN** the loop's own code is read
- **THEN** it SHALL contain no `timeout` of the agent call

#### Scenario: guard and sweep fail fast

- **WHEN** a job that does not run the agent is read
- **THEN** its `timeout-minutes` SHALL be present and at most 30
