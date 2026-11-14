# queued-run-alarm

## ADDED Requirements

### Requirement: Run-level ghost-queue squat classification

Beyond its job-row scan, the queued-run alarm SHALL classify the runs still non-terminal past the
`--minutes` threshold and report them once per episode (issue #2656). A run whose head branch has been
deleted (git ref 404) and that no OPEN pull request tracks SHALL be classified ORPHAN-queued; a run
still `in_progress` whose job records have ALL concluded SHALL be classified EXPIRED and read as JOB
EXPIRY (#1889 wording) — never as a live matrix, and never counted toward the live queued/in_progress
supply. A run with an OPEN pull request, or whose head branch still exists, SHALL be LIVE and not a
squat. A transient head-branch read failure SHALL be treated as present so a live run is never
mis-called orphan. The alarm SHALL NEVER cancel nor delete any run it reports: cancellation is the
owner's explicit word (the handling rule is written in `docs/BOTS.md`).

#### Scenario: an orphan-queued run is reported as an orphan

- **GIVEN** a run queued past the threshold whose head branch is deleted and no OPEN pull request tracks it
- **WHEN** the alarm runs
- **THEN** it SHALL print the run id under "GHOST-RUN SQUAT" as orphan-queued
- **Test:** `tests/test_queued_run_alarm.py::test_an_orphan_queued_run_is_classified_orphan`

#### Scenario: a live run is not a squat

- **GIVEN** a queued run whose head branch still exists, or one an OPEN pull request tracks
- **WHEN** the alarm runs
- **THEN** it SHALL report no ghost-run squat for it
- **Test:** `tests/test_queued_run_alarm.py::test_a_live_queued_run_is_not_an_orphan`,
  `tests/test_queued_run_alarm.py::test_an_open_pr_makes_a_deleted_branch_run_live`

#### Scenario: an expired in_progress run is job expiry, not a live matrix

- **GIVEN** a run still `in_progress` whose job records have all concluded
- **WHEN** the alarm runs
- **THEN** it SHALL report the run as job expiry (#1889) and SHALL NOT count it as a live run
- **Test:** `tests/test_queued_run_alarm.py::test_an_in_progress_run_with_only_concluded_jobs_is_job_expiry`

#### Scenario: a healthy in_progress run is not expiry

- **GIVEN** an in_progress run with live jobs
- **WHEN** the alarm runs
- **THEN** it SHALL not report it as a squat
- **Test:** `tests/test_queued_run_alarm.py::test_a_live_in_progress_run_is_not_expired`

### Requirement: Once-per-episode reporting, and never a cancellation

With `--comment`, the alarm SHALL deliver the squat as ONE deduped issue per EPISODE, keyed on the
sorted run-id set via the marker `queued-run-squat episode <ids>`, so the same squat is reported once
and a newly added run is a fresh episode. It SHALL render through the one issue-body renderer and SHALL
make its delivery failures loud. It SHALL exit 1 when a squat exists (even with no stuck job) and 0
when neither, and SHALL exit 3 when a delivery fails.

#### Scenario: one issue per episode, deduplicated

- **GIVEN** an orphan-queued run and `--comment`
- **WHEN** the alarm runs twice with no change in the run set
- **THEN** the first run files ONE episode issue and a second run files none
- **Test:** `tests/test_queued_run_alarm.py::test_the_squat_is_reported_once_per_episode_and_never_cancelled`

#### Scenario: a squat makes the alarm red even with no stuck job

- **GIVEN** an orphan-queued run and no queued stuck JOB
- **WHEN** the alarm runs
- **THEN** the exit code SHALL be 1
- **Test:** `tests/test_queued_run_alarm.py::test_an_orphan_queued_run_is_classified_orphan`

#### Scenario: the alarm never cancels a run it reports

- **GIVEN** a squat
- **WHEN** the alarm runs with `--comment`
- **THEN** it SHALL issue no `run cancel` and no delete; cancellation is the owner's word
- **Test:** `tests/test_queued_run_alarm.py::test_the_squat_is_reported_once_per_episode_and_never_cancelled`
