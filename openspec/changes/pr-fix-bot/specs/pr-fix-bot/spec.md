# pr-fix-bot

## ADDED Requirements

### Requirement: The repair loop is bounded, stops early, and gives up loudly

The loop SHALL run the failing check, hand the failure and the rules to the agent, re-check, and
repeat up to `FIX_ROUNDS` times (default 3). It SHALL exit 0 as soon as the check is green — on
the first check, without spending an agent round — 1 when the check is still red after the last
attempt, and 2 when it is misconfigured (bad round count, missing rules file or agent), in which
case it SHALL attempt nothing.

#### Scenario: green on the first check costs no round

- **WHEN** the check passes on the first run
- **THEN** the agent SHALL not be invoked and the loop SHALL exit 0

#### Scenario: it stops as soon as the repair sticks

- **GIVEN** the check fails until the agent's second call
- **WHEN** the loop runs with the default rounds
- **THEN** the agent SHALL be invoked exactly twice and the loop SHALL exit 0

#### Scenario: three attempts, then a human

- **GIVEN** the check never passes and the agent changes nothing
- **WHEN** the loop runs
- **THEN** the agent SHALL be invoked exactly three times, the loop SHALL exit 1, and it SHALL
  say it is leaving the PR for a human

#### Scenario: a bad configuration attempts nothing

- **WHEN** `FIX_ROUNDS` is not a positive integer, or the rules file or the agent is missing
- **THEN** the loop SHALL exit 2, name the problem, and not invoke the agent

### Requirement: The agent receives the rules and the failure

The loop SHALL hand the agent the rules file and the tail of the failing command's output, so the
prompt states what is forbidden (mocking, weakening, skipping) as well as what broke.

#### Scenario: rules and failure travel together

- **WHEN** the check fails with a recognisable message
- **THEN** the agent's input SHALL contain that message and the rules' prohibitions

### Requirement: The loop never publishes

The loop SHALL NOT commit, stage, push, merge, rebase or otherwise modify git state; publishing
is the workflow's job, and only when the loop exits 0.

#### Scenario: a red run leaves the repository untouched

- **GIVEN** a git repository and a check that never passes
- **WHEN** the loop runs
- **THEN** `HEAD` SHALL be unchanged, nothing SHALL be staged, and the loop SHALL not push

### Requirement: A scheduled sweep decides which PR the bot repairs

The bot SHALL be started by a **scheduled sweep**, not by a conditional job in the pipeline:
issue #107 forbids a CI job that can skip itself, so the decision SHALL live in
`scripts/fix_bot_sweep.py`. It SHALL consider only open, non-draft, same-repo PRs (a fork branch
cannot be pushed to), never the base branch, only PRs with at least one failing check, and only
branches carrying fewer than three `fix(bot):` commits — capped so a repair that does not stick
cannot loop — and it SHALL repair at most one PR per sweep, oldest-updated first, reporting the
reason for every PR it passes over.

#### Scenario: a fork or a draft is skipped

- **GIVEN** a pull request whose head repository is not this repository, or a draft
- **WHEN** its checks fail
- **THEN** the dispatch job SHALL not run

#### Scenario: the cap is reported, not looped

- **GIVEN** a branch that already carries the maximum number of fix-bot commits
- **WHEN** its checks fail again
- **THEN** the job SHALL comment on the PR that the bot will not run again, and SHALL NOT dispatch

### Requirement: The bot repairs, reports, and never merges

The fix-bot workflow SHALL push the repaired working tree as one commit using the owner PAT (so
CI re-runs on the new head), SHALL comment the outcome on the PR, and SHALL NOT merge. A run that
leaves the check red SHALL push nothing and say so, quoting the failure.

#### Scenario: green pushes once and CI re-runs

- **WHEN** the loop ends green with a changed tree
- **THEN** the workflow SHALL push exactly one commit with the PAT and comment the outcome

#### Scenario: red pushes nothing

- **WHEN** the loop ends red
- **THEN** the workflow SHALL push nothing and comment the failing output for a human

#### Scenario: no agent means a loud failure

- **WHEN** the Hermes CLI cannot be installed
- **THEN** the install step SHALL fail loudly rather than let the loop report a false "still red"
