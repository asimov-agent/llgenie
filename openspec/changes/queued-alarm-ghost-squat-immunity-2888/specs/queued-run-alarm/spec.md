# queued-run-alarm

## ADDED Requirements

### Requirement: Confirmed-concluded ghosts are named, never counted (issue #2888)

The run-level squat scan SHALL read the zero-job retirement ledger
(`check_zero_job_pending.zombie_retired_run_ids(repo)`, the #2600 mechanism) once per scan BEFORE any
per-candidate round-trip: a candidate whose run id is in the ledger SHALL be reported in a named
`retired` list and SHALL NOT be counted toward the squat episode, SHALL NOT affect the exit code, and
the squat scan SHALL spend no jobs, branch, or PR round-trip on it (the job-level stuck scan keeps the
per-run jobs read it always had, which names jobless rows without counting them). A non-ledger candidate that is orphan-queued (head
branch deleted, no OPEN pull request) AND older than GitHub's own 24h queued window AND whose job
records include at least one instantiated job with ALL instantiated jobs concluded SHALL be classified
CONFIRMED-CONCLUDED GHOST: named in its own report bucket, never counted as squat, never cancelled,
never filed. A candidate that instantiated no jobs, or whose jobs are not all concluded, stays a live
squat exactly as classified today (ORPHAN-queued / EXPIRED), still RED and still filed. The alarm
SHALL still never cancel or delete any run. The scan SHALL also accept a `--dry` switch that performs
the full read and prints the full report while filing nothing and producing the same exit code — the
principal local proofs (and any host-side replay) run under (the scheduled lane keeps the filing
behaviour it has today).

#### Scenario: ledger-retired rows cannot redden the lane

- **GIVEN** a queued run list whose squat candidates are all ids present in the retirement ledger
- **WHEN** the alarm runs
- **THEN** it SHALL name them as retired, exit clean, file no squat issue, and spend no `run view`,
  branch, or PR round-trip from the squat scan on them
- **Test:** `tests/test_queued_run_alarm.py::test_ledger_retired_runs_are_named_and_never_counted`

#### Scenario: a ghost with concluded jobs is confirmed, not counted

- **GIVEN** an orphan-queued run older than 24h whose one instantiated job is `completed` while its
  row is still non-terminal (the measured `43096752585` shape)
- **WHEN** the alarm runs
- **THEN** it SHALL report the run under "confirmed-concluded ghost" and exit clean with no filing
- **Test:** `tests/test_queued_run_alarm.py::test_a_ghost_with_all_jobs_concluded_is_named_never_counted`

#### Scenario: a live orphan squat is still RED and still filed

- **GIVEN** an orphan-queued run past the threshold that instantiated no jobs (no runner ever arrived)
- **WHEN** the alarm runs
- **THEN** it SHALL count it as orphan squat, exit non-zero, and file the episode exactly as today
- **Test:** `tests/test_queued_run_alarm.py::test_a_live_orphan_queued_run_still_reddens_the_lane`

#### Scenario: a mixed scan names every ghost and counts only live squat

- **GIVEN** a run list containing one ledger-retired id, one concluded-ghost id, and one live
  orphan-queued id
- **WHEN** the alarm runs
- **THEN** it SHALL name all three, count only the live one, and file an issue only for the live one
- **Test:** `tests/test_queued_run_alarm.py::test_a_mix_names_ghosts_and_counts_only_live_squat`
