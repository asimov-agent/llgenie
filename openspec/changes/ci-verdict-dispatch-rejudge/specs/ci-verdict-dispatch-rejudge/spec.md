# ci-verdict-dispatch-rejudge

## ADDED Requirements

### Requirement: a manual dispatch re-judges a named finished run through the same judge steps

The judge MUST be reachable by a `workflow_dispatch` carrying a `run_id` input, so an operator can
re-judge one finished run without re-running its CI fan-out. The dispatch path MUST run the same
`judge` steps as the `workflow_run` path and resolve `RUN_ID`, `HEAD_SHA` and the concurrency group
key from the dispatch input when present, else from `github.event.workflow_run`.

WHEN ci-verdict.yml receives a `workflow_dispatch` with `inputs.run_id`
THEN it judges that run's jobs and decision and posts a fresh check-run, without re-running the run

#### Scenario: a dispatch re-judges the named run and posts a fresh check-run

- **Given** a finished run whose `run_id` is passed as the dispatch input
- **When** an operator dispatches `ci-verdict.yml` with that `run_id`
- **Then** the `judge` job reads that run's jobs and decision and posts a `ci-verdict` check-run on
  the head, and no job of the judged run is re-executed

### Requirement: the auto workflow_run path is unchanged

The `workflow_run` auto-judge MUST behave exactly as before: fires on `CI` `completed`, `RUN_ID` is
`github.event.workflow_run.id`, `HEAD_SHA` is `github.event.workflow_run.head_sha`, and the concurrency
group is keyed on that run id with `cancel-in-progress: false`.

WHEN a `CI` run completes
THEN the workflow_run path resolves RUN_ID and HEAD_SHA from the event as before and judges the run

#### Scenario: the auto path resolves from the workflow_run event

- **Given** a completed `CI` run
- **When** ci-verdict.yml's `workflow_run` trigger fires
- **Then** `RUN_ID` and `HEAD_SHA` resolve from `github.event.workflow_run` and the verdict is judged
  and posted exactly as before the dispatch addition

### Requirement: the dispatch re-judge never re-runs the judged run and never edits a branch

The manual path MUST NOT re-run the judged CI run, MUST NOT push or edit any branch, and MUST NOT
read a repository secret. Its only side effects are reading the run's jobs + decision and posting a
check-run.

WHEN a dispatch re-judge runs
THEN it performs no CI re-run, no branch write and no secret read

#### Scenario: re-judge side effects are read-only plus a check-run post

- **Given** the workflow's `permissions: contents: read, actions: read, checks: write` and no `if:`
  that skips the judge
- **When** the dispatch re-judge runs
- **Then** the only side effects are reading the named run's jobs + decision and posting its check-run
