# queued-starvation-doc

## ADDED Requirements

### Requirement: A starved queue is distinguishable from a broken PR, in writing

`docs/BOTS.md` SHALL state that a repo-wide `queued` state with no `in_progress` runs is runner supply, not a
PR defect, SHALL give the commands that measure it, SHALL distinguish it from a single PR whose rollup is
empty because the branch conflicts, and SHALL state that pushing to drain a queue re-queues the matrix.

WHEN a reader faces a `BLOCKED` PR whose checks have not run
THEN the doc tells them how to decide between supply and a defect, and what not to do.

#### Scenario: the reader measures supply first

Given every open PR reads `BLOCKED` and no check has completed
When  the reader runs `gh run list --limit 100 --json status`
Then  many `queued` with zero `in_progress` identifies a starved queue, and the documented remedy is to wait,
      not to rebase or merge.

#### Scenario: one PR's empty rollup is not a queue problem

Given one PR has no checks and `mergeStateStatus: DIRTY`
When  the reader consults the same section
Then  it names that case as a branch needing a rebase (#801), not as supply.
