# Zero-job job-count read

## ADDED Requirements

### Requirement: The zero-job count is read from the jobs array, not a key the projection lacks

The monitor `check_zero_job_pending.py` decides whether a dispatched run is stranded by its
instantiated-jobs count. The count must come from the `jobs` list that `gh run view --json jobs`
returns (`len(jobs["jobs"])`), never from a `total_count` key of that projection, because the
projection emits `{"jobs":[...]}` with no `total_count` key (measured 2026-11-06) and reading the
absent key yields `0` for every run.

#### Scenario: a run with live jobs is not reported as zero-job

Given a `workflow_dispatch` run older than the `--minutes` threshold whose `gh run view --json
jobs` answer is `{"jobs":[{...},{...},{...}]}` (three live jobs, e.g. run `42141213441`),
when `check_zero_job_pending.py --file` runs,
then the run is NOT reported as "zero jobs" and no issue is filed for it.

#### Scenario: a genuinely jobless run is still reported once

Given a `workflow_dispatch` run older than the `--minutes` threshold whose jobs list is empty and
whose concurrency group is free (not queued behind an in-progress sibling),
when `check_zero_job_pending.py --file` runs,
then the run IS reported as a stranded zero-job run and one deduped issue is filed for it
(`--file`), forced RED via the ci-verdict path.

#### Scenario: the queued-behind discriminator is unchanged

Given a zero-job run queued behind an in-progress sibling holding the same (workflow, branch)
concurrency group (the #1704 class),
when `check_zero_job_pending.py` runs,
then the run is NOT reported — it is waiting its turn, not short of runners.

### Requirement: Exit contract is preserved

The monitor keeps its exit codes: 0 = no stranded zero-job run; 1 = at least one stranded
(`--file` files it); 2 = GitHub read failed; 3 = delivery failed. The monitor never weakens a
gate, never merges, never cancels a run, and never runs in a pull request.

#### Scenario: read failure is UNKNOWN, never clean

Given `gh` fails to answer the run read,
when `check_zero_job_pending.py` runs,
then it exits 2 (a real GitHub read failure is never dressed up as "no stranded runs").
