# queued-run-alarm

## ADDED Requirements

### Requirement: the squat detector reads the zero-job retirement ledger (issue #2600)

Beyond its job-row scan and the run-level orphan/expired classification, `squat_runs()` SHALL read
the one zero-job zombie-retirement ledger (`check_zero_job_pending.zombie_retired_run_ids(repo)` —
the shared record of confirmed-concluded phantom rows, issue #2600) and report a candidate run whose
id is in it as `retired (confirmed concluded earlier, #2600 mechanism; admin-only row, see #2606)`.

WHEN a non-terminal-looking run's id is already retired in the ledger,
THEN it SHALL be reported as RETIRED — named but never counted, never cancelled, never filed, and
never given a `run view` round-trip by `squat_runs`.

#### Scenario: a ledger-retired run is named but never counted

- **GIVEN** a queued run whose id carries a `zero-job-zombie-retired` retirement marker in an issue body
- **WHEN** the alarm runs
- **THEN** it SHALL exit 0, print it as RETIRED naming the #2600 mechanism and the #2606 admin-only
  row, and spend no `run view` round-trip on it beyond `stuck_jobs`'s own job-row scan
- **Test:** `tests/test_queued_run_alarm.py::test_a_ledger_retired_run_is_named_but_never_counted`

### Requirement: a read-only confirmed-concluded probe for non-ledger ghosts (issue #2600)

WHEN a run row is past the 24h queue-expiry window (`QUEUE_EXPIRY_MINUTES`) AND is ORPHANED (no open
PR, head branch deleted) AND all its instantiated jobs have concluded,
THEN it SHALL be reported as a CONFIRMED-CONCLUDED GHOST — named but never counted, never cancelled,
never filed. This is the probe that catches a run (like `43096752585`) that has jobs, so the zero-job
gate's retirement can never retire it.

#### Scenario: an orphaned run past 24h with all jobs concluded is a never-counted ghost

- **GIVEN** an orphaned run (deleted head branch, no open PR) older than 24h whose one job is `completed`
- **WHEN** the alarm runs
- **THEN** it SHALL exit 0, print it as a CONFIRMED-CONCLUDED GHOST, and never cancel it
- **Test:** `tests/test_queued_run_alarm.py::test_a_confirmed_concluded_ghost_is_named_but_never_counted`

#### Scenario: retired and confirmed-concluded ghosts are never filed as a squat

- **GIVEN** a confirmed-concluded ghost and `--comment`
- **WHEN** the alarm runs
- **THEN** it SHALL exit 0 and file no squat episode issue for it
- **Test:** `tests/test_queued_run_alarm.py::test_a_ledger_retired_or_confirmed_ghost_is_never_filed`

### Requirement: live squat semantics are unchanged (issue #2600, #2656)

WHEN a queued run is orphaned but a job is still pending (not all concluded),
THEN it SHALL stay a RED live-orphan finding, filed exactly as today — the confirmed-concluded probe
must never swallow a run that may genuinely be waiting on a runner.

#### Scenario: a live orphan with a pending job is still red and still filed

- **GIVEN** an orphaned run with a still-`queued` job, and `--comment`
- **WHEN** the alarm runs
- **THEN** it SHALL exit 1, print it as orphan-queued, and file the squat episode issue
- **Test:** `tests/test_queued_run_alarm.py::test_a_live_orphan_with_pending_jobs_is_still_red`
