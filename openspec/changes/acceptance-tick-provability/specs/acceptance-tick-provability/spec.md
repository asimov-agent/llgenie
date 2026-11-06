# Acceptance-tick provability — fold/sync acceptance ticks need replayable evidence

## ADDED Requirements

### Requirement: a ticked acceptance criterion must name replayable evidence

`check-pr-acceptance` reds an issue-side TICKED criterion whose `(proven: …)` evidence names
neither a CI run id (`run=<id>`) nor a reproducible command with its exit code and the measured tree
sha (`proven: <command> rc=<n> <sha>`).

#### Scenario: a fold/sync tick names only a hash/compare

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion
When the criterion's `(proven: …)` text names a byte-compare/sync-check but neither `run=` nor `rc=`
Then `check-pr-acceptance` reports a `tick-unprovable` finding
And the merge is held (non-zero exit), exactly like an unticked criterion

#### Scenario: a tick names a CI run id

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion
When the criterion's `(proven: …)` text names `run=<id>`
Then no `tick-unprovable` finding is raised
And the read of that criterion stands on the named live run

#### Scenario: a tick names a reproducible command + rc + sha

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion
When the criterion's `(proven: …)` text names a command with `rc=<n>` and a tree sha
Then no `tick-unprovable` finding is raised
And re-running that one command at that sha reproduces the proof (the drift lamp)

#### Scenario: a bare tick with no evidence

Given a linked issue whose `## Acceptance criteria` has a `- [x]` criterion with no `(proven: …)` line
Then `check-pr-acceptance` reports a `tick-unprovable` finding
And the self-tick (#745 class) stays held

### Requirement: the gate reads, it never writes

The `tick-unprovable` class is a verification finding only; no write-back semantics change.

#### Scenario: write-back is untouched

Given a PR whose issue has an unprovable tick
When the gate reports it
Then `acceptance_writeback` semantics are unchanged (#1644)
And the gate only holds the merge until evidence is recorded or the tick is removed

## MODIFIED Requirements

### Requirement: `check-pr-acceptance` reports an unchecked-close violation

The existing `acceptance-unchecked` and `acceptance-exceeds` findings remain, and are joined by the
new `tick-unprovable` class.

#### Scenario: all three classes coexist

Given a linked issue with both an unticked criterion and a ticked-but-unprovable criterion
When the gate runs
Then both an `acceptance-unchecked` and a `tick-unprovable` finding are reported
And the merge exits non-zero
