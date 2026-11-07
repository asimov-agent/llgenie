# ci-verdict-judge-waits-for-settled-run

## ADDED Requirements

### Requirement: the judge refuses a mid-upload run snapshot instead of producing a verdict from it

The judge MUST NOT derive a verdict from a jobs listing that contains any job whose `status` is
not `completed`. A `workflow_run` `completed` event can fire while the run's own job rows are
still settling (`in_progress`/`queued`, a job mid-upload with no `conclusion`), and counting such
a row as `pending`/absent posts a false `no_verdict` for a run that is not done. When the run-id
path reads a jobs list that contains an unsettled job, the judge MUST refuse the read, name the
unsettled job, and exit `2` ("could not reach a verdict") — never a posted verdict on the head.

WHEN the judge reads a run whose jobs listing contains a job with `status != completed`
THEN it reports that the run is not settled and exits 2 without producing or posting a verdict

#### Scenario: a job is mid-upload when the judge reads the run

- **Given** a decided run whose jobs list still carries one row with `status: in_progress` and no
  `conclusion`
- **When** the judge runs against that run
- **Then** it names the unsettled job and exits 2, and no `ci-verdict` check-run is posted for it

### Requirement: a fully settled run is judged exactly as before

When every job in the run's listing reports `status: completed`, the judge MUST proceed exactly as
today: `ci_scope.verify()` holds the settled rows to the decision, and the exit code reflects only
that verdict (`0` green/neutral, `1` red, `2` error). The settle gate never weakens a real red and
never turns a reached verdict into an error.

WHEN the judge reads a run whose every job reports `status: completed`
THEN it verifies and posts the verdict exactly as before the settle gate existed

#### Scenario: a genuine red run stays red through the settle gate

- **Given** a completed run whose `linux / unit` failed
- **When** the judge verifies it (every job `completed`)
- **Then** the verdict is `red` with the failing gate named, exit 1, exactly as today

#### Scenario: an absent decision stays a legitimate `none`

- **Given** a genuinely cancelled run with no `ci-scope-decision` artifact and all job rows
  `completed`
- **When** the judge verifies it
- **Then** the verdict is `none` (red), because no decision says a skip is legitimate — unchanged
