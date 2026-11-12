# zero-job-pending

## ADDED Requirements

### Requirement: a stranded zero-job run is CLEARED, not only named

When `scripts/check_zero_job_pending.py` runs with `--cancel-stranded`, every run it classifies as
stranded (zero jobs instantiated, past the `--minutes` threshold, not queued behind an `in_progress`
sibling of the same workflow+branch — the #1704 discriminator) MUST be cancelled via
`gh run cancel`, INCLUDING runs already named by an earlier monitor filing. The already-filed skip
must never protect a zombie from clearing: a run filed once and skipped by every later monitor run
stays `pending` forever because GitHub does not evict zero-job runs by itself (issue #1410).

#### Scenario: an already-filed stranded run is cancelled by the next monitor run

- **Given** a run whose dedupe marker is already in an open issue body (filed by a previous monitor
  filing) and which is still `queued` with zero jobs past the threshold
- **When** the monitor runs with `--file --cancel-stranded`
- **Then** the run is NOT re-filed and NOT re-forced RED (the marker still dedupes the delivery)
- **And** `gh run cancel <run-id>` is invoked for it

#### Scenario: a run that finally got a runner is never cancelled

- **Given** a classified stranded run whose jobs re-read, immediately before cancelling, reports at
  least one instantiated job (a runner finally arrived after classification)
- **When** the monitor runs with `--cancel-stranded`
- **Then** the cancel is skipped for that run and the report names it as skipped, so a live compile is
  never touched (the #1822/#1823 class)

#### Scenario: a benign queued-behind run is never cancelled

- **Given** a `queued` zero-job run whose (workflow, branch) pair has an `in_progress` sibling holding
  the concurrency group (the #917/#1704 serialisation case)
- **When** the monitor runs with `--cancel-stranded`
- **Then** the run is neither reported, filed, nor cancelled

### Requirement: the unattended monitor carries the clearing action

The Makefile target `check-zero-job-pending` MUST translate `CANCEL=1` into `--cancel-stranded` (by
reference in the recipe, like the existing `FILE` knob), and `.github/workflows/zero-job-pending.yml`
MUST invoke it with `FILE=1 CANCEL=1` so the scheduled monitor both names AND clears the zombies it
finds.

#### Scenario: the gate the CI leg runs

- **Given** the `zero-job-pending` monitor workflow
- **When** its monitor step runs `make check-zero-job-pending REPO=<owner/repo> MINUTES=30 FILE=1 CANCEL=1`
- **Then** the recipe passes `--file --cancel-stranded` to `scripts/check_zero_job_pending.py`
- **And** `make check-wiring` still reports the script wired to a target and its test module tested

#### Scenario: the filed issue states the automatic remedy

- **Given** a stranded run filed by the monitor with `--cancel-stranded` enabled
- **When** the issue body is rendered
- **Then** its `How we fix it` names the automatic remedy (the monitor cancels the stranded zero-job
  run; re-dispatch once a runner exists) beside the manual runner-fix step
