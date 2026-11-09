# Scheduled engine/registry maintenance jobs

## ADDED Requirements

### Requirement: every scheduled step job declares a `timeout-minutes`

**When** a workflow runs on a `schedule` trigger (`on.schedule`)
**and** one of its `jobs:` entries runs steps (has a `steps:`/`run:` block — not a `uses:` caller),
**then** that job MUST declare a `timeout-minutes` bound, and `scripts/check_workflows.py`'s
`check_scheduled_job_timeouts` MUST report it as a violation when it does not.

#### Scenario: a scheduled step job with a ceiling passes

**Given** a `schedule`-triggered workflow whose job declares `timeout-minutes: 30`,
**when** `check_scheduled_job_timeouts` is run,
**then** the workflow job is not reported as a violation.

#### Scenario: a scheduled step job without a ceiling is reported

**Given** a `schedule`-triggered workflow whose job has no `timeout-minutes`,
**when** `check_scheduled_job_timeouts` is run,
**then** it fails naming the workflow and the job.

#### Scenario: a scheduled uses caller is skipped

**Given** a `schedule`-triggered workflow whose job is a `uses:` caller (which cannot hold a
ceiling, #882),
**when** `check_scheduled_job_timeouts` is run,
**then** the caller is not reported.

#### Scenario: a non-scheduled workflow is out of scope

**Given** a workflow that does not trigger on `schedule`,
**when** `check_scheduled_job_timeouts` is run,
**then** the workflow's jobs are not reported.

### Requirement: the named maintenance jobs carry ceilings sized to their real runs

**Given** the four maintenance step jobs
**when** their `timeout-minutes` are read from the workflow files at the head of this change,
**then** `engine-bump` `plan` = 20, `engine-bump` `bump` = 30, `engine-bump-rebase` `rebase` = 20,
`registry-sync` `sync` = 60 — each a wide but bounded ceiling above the job's measured wall time.

#### Scenario: the negative control reddens a dropped ceiling

**Given** the fixed tree with `registry-sync.yml` `sync`'s `timeout-minutes: 60` removed,
**when** `make check-workflows` is run,
**then** it reds with rc=1 naming `registry-sync.yml`/`sync`, and passes green (rc=0) once the
ceiling is restored.
