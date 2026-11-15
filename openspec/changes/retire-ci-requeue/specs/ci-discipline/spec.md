## REMOVED Requirements

### Requirement: ci-requeue-cancelled re-runs superseded-free cancelled runs (lane: ci-requeue.yml)

Reason: the owner's CI-discipline policy (issue #2701) forbids any repo mechanism that starts a CI
pipeline outside GitHub events and the allow-listed weekly engine lane. `make ci-requeue-cancelled`,
`scripts/ci_requeue.py` and `.github/workflows/ci-requeue.yml` are a `gh run rerun` requeue loop.

#### Scenario: no requeue surface remains

- **WHEN** the tree is searched for `ci_requeue`, `ci-requeue-cancelled` and `ci-requeue.yml`
- **THEN** no script, workflow, make target, test, inventory or active doc names them (archived
  openspec change records are the only historical mentions)

## ADDED Requirements

### Requirement: a CI run rerun is a human GitHub-UI action

The repo SHALL NOT contain any mechanism — script, make target, or scheduled workflow — that calls
`gh run rerun` (or dispatches a workflow) to re-run CI runs, except the allow-listed lanes of
issue #2701 (`ci-frozen-reaper`, the engine lane, the latest-models/inference-servers lane). The
tools that report a PENDING (cancelled) verdict SHALL name the human-UI rerun rule, not a repo
rerun target.

#### Scenario: pending-verdict text names the human rule

- **WHEN** `run-failure-reactor.py` reports a cancelled run or `fix_bot_sweep.py` prints a PENDING
  cancellation
- **THEN** the output says a rerun belongs to the GitHub UI (issue #2702) and names no make rerun
  target

#### Scenario: zero-job-pending rides an allow-listed lane

- **WHEN** `zero-job-pending.yml` is read
- **THEN** its only trigger is `workflow_run` on `ci-frozen-reaper` (completed), and no roster name
  refers to the retired lane
