# engine-build-pr-trigger-head-sha

## ADDED Requirements

### Requirement: a rebased PR head's trigger run is scoped to its own head SHA

The `concurrency` group key in `.github/workflows/engine-build-pr-trigger.yml` MUST include the PR
head commit SHA (`${{ github.event.pull_request.head.sha }}`) in addition to the PR number, and MUST
keep `cancel-in-progress: false`. The group key MUST be
`engine-build-pr-trigger-${{ github.event.pull_request.number }}-${{ github.event.pull_request.head.sha }}`.
No other gate, guard, or dispatch step in the workflow is changed by this requirement.

WHEN a `synchronize` push updates a PR head while an older head's producer build is still running
THEN a new trigger run for the new head MUST start (its `guard` job present) instead of being queued
behind the old head's run with no jobs.

#### Scenario: rebased head gets a real guard job immediately

- **Given** `.github/workflows/engine-build-pr-trigger.yml` with the head-SHA-scoped concurrency key
- **When** a PR is updated (`synchronize`) while its old head's producer is still building
- **Then** the new trigger run reports a `guard` job immediately (job present), not the
  `pending`/0-jobs concurrency-queued signature
- **Test:** verified on a rebased pin-bump PR (engine-build-pr-trigger caveat; the measured victim
  was run `42163068853` @ `321dabc826` behind run `42155990380`)

#### Scenario: never-cancel preserved

- **Given** the head-SHA-scoped concurrency key
- **When** a stale head's trigger could be superseded
- **Then** `cancel-in-progress: false` is preserved, so a live producer run is never cancelled and no
  `engine-build.yml` guard/gate/queue is changed

### Requirement: the new head dispatches its own producer run

A trigger run for a rebased head MUST dispatch its own `engine-build push=true` producer run — a
`workflow_dispatch` run exists at that head's SHA — without requiring `gh run rerun` on any
concurrency-queued run.

WHEN a new-head trigger run starts
THEN it dispatches its own producer run at its head SHA, independently of any competing older-head run.

#### Scenario: a rebased head dispatches its own producer without rerun

- **Given** a new-head trigger run starts (concurrency key carries the head SHA)
- **And** an older head's producer is still building on the same PR
- **When** the new-head trigger's `make engine-build-pr-trigger` step runs
- **Then** it dispatches a `workflow_dispatch` `engine-build push=true` run at the new head's SHA without needing `gh run rerun` on any concurrency-queued run
