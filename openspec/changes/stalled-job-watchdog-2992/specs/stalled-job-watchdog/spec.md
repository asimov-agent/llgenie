## ADDED Requirements

### Requirement: a concluded-sibling run with an in_progress job past its budget is named, once, on its PR
When a CI run is `in_progress`, has at least one job already concluded, and an `in_progress` job has
been running longer than `max(STALL_FLOOR, STALL_FACTOR × median wall time of that job name in the
same workflow's recent completed runs)` (floor 15 minutes, factor 1.25; `FALLBACK_MINUTES=60` when the
job name has no completed history), the stalled-job watchdog SHALL flag that run+job and print the job
name, its elapsed minutes, the budget and its derivation. With `--file` it SHALL post exactly one
comment on the PR whose head the run carries, ending with the dedupe marker
`<!-- stalled-job-watchdog: run <id> job <job-id> -->`, and SHALL NOT post a second comment for the
same run+job when the marker is already present on that PR. It SHALL NOT cancel, re-run, or otherwise
touch the run.

#### Scenario: the measured hung-unit wedge is flagged
- **WHEN** a fixture run has one concluded job and one `in_progress` job older than its budget (the
  measured shape of run `44863652918`: `linux/unit` `in_progress` since 03:57:56Z while every sibling
  concluded at 03:57Z)
- **THEN** exactly one finding names the job and its elapsed time, and with `--file` exactly one
  comment lands on the PR carrying that head

#### Scenario: a job within its budget is not flagged
- **WHEN** a fixture run's only `in_progress` job has been running shorter than the budget derived
  from that job name's median wall time
- **THEN** no finding is printed and no comment is posted

#### Scenario: the marker makes the sweep replay no second comment
- **WHEN** the PR's comments already carry `stalled-job-watchdog: run <id> job <job-id>` for that
  finding
- **THEN** the replay names the finding as already commented and posts nothing new

### Requirement: runs the other lanes own are left alone
A run whose jobs are all still `in_progress` (nothing concluded) SHALL NOT be flagged by this watchdog;
job-less pending runs stay with `check_zero_job_pending.py` (#1410) and the queued alarm (#917), and
fully frozen runs stay with `ci_frozen_reaper.py`. A finding whose run belongs to no PR (a push or
schedule run) SHALL be named in the report only, never filed as an issue.

#### Scenario: an all-in_progress run is not a stalled-job finding
- **WHEN** a fixture run has two jobs, both `in_progress`, one far past any budget
- **THEN** the watchdog reports no stalled-job finding for it

### Requirement: the exit codes stay the lane's contract
The watchdog SHALL exit 0 when nothing new needs action (no findings, or all findings already named or
successfully commented), 1 when findings exist and `--file` was not given, 2 when a GitHub read fails,
and 3 when a comment delivery fails; the lane step runs it with `--file`.

#### Scenario: findings without --file exit 1
- **WHEN** a stalled finding exists and `--file` is absent
- **THEN** the exit is 1 and the report names the finding
