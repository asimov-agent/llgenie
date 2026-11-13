# Acceptance-tick provability — a cited run must be a GREEN run at the live head

## MODIFIED Requirements

### Requirement: a ticked acceptance criterion must name replayable evidence

`check-pr-acceptance` reds an issue-side TICKED criterion whose `(proven: …)` evidence names
neither a CI run id (`run=<id>`) nor a reproducible command with its exit code and the measured tree
sha (`proven: <command> rc=<n> <sha>`). Since issue #2288 the `run=` branch is no longer a bare
regex pass: every cited `run=<id>` is looked up LIVE (`gh api repos/<repo>/actions/runs/<id>`,
through the gate's `--gh` seam) and judged by its conclusion and the head it belongs to.

#### Scenario: a tick cites a run that concluded failure or cancelled

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion
When the criterion's `(proven: …)` text names `run=<id>` and that run's live conclusion is
`failure` or `cancelled`
Then `check-pr-acceptance` reports a BLOCKING `tick-cites-red-run` finding
And the finding names the run id, its conclusion, the head that run belongs to, and the current head
(the head a red run belongs to is NEVER accepted as the criterion's head)

#### Scenario: a tick cites a run that has not concluded

Given a TICKED criterion whose `(proven: …)` names `run=<id>` and that run is still
`queued`/`pending`/`in_progress`
Then the gate reports the criterion as the NON-red `acceptance-proven-awaiting-writer` state
And the merge is not held, but the criterion is never counted as proven-green

#### Scenario: a tick cites a GREEN run at a head other than the current one

Given a TICKED criterion whose `(proven: …)` names `run=<id>` whose conclusion is `success`
but whose `head_sha` differs from the gate's current revision
And the `(proven: …)` text names no head sha matching the current revision
Then `check-pr-acceptance` reports a BLOCKING `tick-stale-head-unflagged` finding
And the finding names the stale head and the live head

#### Scenario: a stale head is flagged by naming the live head alongside it

Given a TICKED criterion whose `(proven: …)` names a head sha at which the proof was measured
AND also names the gate's current revision sha
Then no stale-head finding is raised (the marker recorded the live head at measurement time)

#### Scenario: a ticked criterion's head=<sha> token drifted and is unflagged

Given a TICKED criterion whose `(proven: …)` carries a `head=<sha>` token (or tokens)
And NO named sha (head token or cited green run's `head_sha`) equals the gate's current revision
Then `check-pr-acceptance` reports a BLOCKING `tick-stale-head-unflagged` finding
And the drift is named, never passed silently

#### Scenario: the live run lookup is unreadable

Given a TICKED criterion citing `run=<id>`
When the `gh api` lookup of that run fails
Then the gate reports a BLOCKING `tick-run-unreadable` finding naming the run id
And an unreadable lookup is never treated as proven

#### Scenario: rc+sha commands are not run-looked-up

Given a TICKED criterion whose `(proven: …)` names only a command with `rc=<n>` and a sha
Then no run lookup happens and the existing reproducible-command rule decides the tick

## ADDED Requirements

### Requirement: the gate resolves the revision it measures

`check-pr-acceptance` resolves `--rev` to a concrete sha (`git rev-parse`) before judging head
staleness; when the revision cannot be resolved (fixture runs without a git checkout), the
stale-head class is skipped and every other rule still applies.

#### Scenario: HEAD on a real checkout

Given the scope job running `make check-pr-acceptance` in the PR checkout
Then the stale-head comparisons run against `git rev-parse HEAD` of that checkout
