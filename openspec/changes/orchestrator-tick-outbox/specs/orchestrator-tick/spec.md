# orchestrator-tick

## ADDED Requirements

### Requirement: the outbox is written before the durable state advances

`scripts/orchestrator_tick.py emit` MUST append the delta records to the append-only outbox and
`fsync` it BEFORE it reads or writes the durable state that records which facts it has already
handled. Records already present in the outbox MUST NOT be appended twice: the delta is the facts
the state and the outbox do not already carry. A delivery that cannot be completed (the print fails)
MUST leave its records pending rather than acknowledged, and MUST exit non-zero.

#### Scenario: a lost delivery is re-emitted verbatim by the next pass

- **Given** an outbox and a state that do not exist yet, and a repository whose only fact is
  `REBASE-NEEDED #919 @e21e7b22 mergeStateStatus=DIRTY`
- **When** the producer emits with its stdout discarded and does not acknowledge (`--no-ack`)
- **Then** the outbox holds exactly one record, the state records the fact as handled, and the next
  emit prints the SAME line byte-for-byte, including the `[measured …]` stamp of the first run
- **Test:** `tests/test_orchestrator_tick.py::test_a_lost_delivery_reemits_the_same_lines`

#### Scenario: the outbox is durable when the state write fails

- **Given** a state path that cannot be written
- **When** the producer emits a new fact
- **Then** the outbox already carries the record, the exit code is non-zero, and a later emit with a
  writable state prints the line once and does not duplicate the record
- **Test:** `tests/test_orchestrator_tick.py::test_the_outbox_is_written_before_the_state_advances`

#### Scenario: a failed read is loud and leaves both files untouched

- **Given** an outbox and a state from an earlier pass
- **When** `gh` fails
- **Then** the producer exits 2 and both files are byte-identical to what they were
- **Test:** `tests/test_orchestrator_tick.py::test_a_failed_read_fails_loud_and_leaves_the_outbox_and_state_untouched`

### Requirement: every emitted line carries the measurement time of the fact it reports

Each emitted line MUST end with `[measured HH:MM:SSZ]`, taken from the measurement of THAT fact and
persisted in the outbox record, never from the clock at emit time. A re-emitted line therefore keeps
the original stamp, so its age is visible without re-measuring the subject.

#### Scenario: a re-emitted line keeps the first run's stamp

- **Given** a first emit at 21:14:07Z whose delivery was lost
- **When** the next emit runs at 21:31:52Z
- **Then** the line still reads `[measured 21:14:07Z]`, not `[measured 21:31:52Z]`
- **Test:** `tests/test_orchestrator_tick.py::test_a_reemitted_line_carries_the_measurement_time_of_the_fact`

### Requirement: a merged pull request or a closed issue is never emitted

At emit time — not from the state, not from a remembered queue — the producer MUST ask the subject's
live state (`gh pr view <n> --json state,mergedAt`, `gh issue view <n> --json state`). A fact whose
PR is not `OPEN` or carries a `mergedAt`, and a fact whose issue is not `OPEN`, MUST NOT appear on
stdout, MUST be recorded as suppressed, and MUST NOT be emitted by any later pass.

#### Scenario: a pull request that merged between measurement and emit is suppressed

- **Given** a fact measured while PR #919 was open and `DIRTY`
- **When** the same subject reports `state=MERGED, mergedAt=…` at emit time
- **Then** stdout is empty, the fact is recorded as suppressed, and the next pass's stdout is empty too
- **Test:** `tests/test_orchestrator_tick.py::test_a_merged_pull_request_is_not_emitted`

#### Scenario: an issue that closed between measurement and emit is suppressed

- **Given** an `IMPLEMENT-READY #1049` fact measured while the issue was open
- **When** the same subject reports `state=CLOSED` at emit time
- **Then** stdout is empty and the fact is recorded as suppressed
- **Test:** `tests/test_orchestrator_tick.py::test_a_closed_issue_is_not_emitted`

### Requirement: the delta key is the fact set, never the run time

The delta MUST be keyed on the measured fact (`<KIND> #<subject> <detail>`, where a PR's detail
carries its head sha and merge state), never on the run's clock. A second pass over unchanged state
MUST emit nothing, append nothing, and leave the outbox byte-identical.

#### Scenario: an unchanged second pass is silent and writes nothing

- **Given** a first emit that delivered and acknowledged one fact
- **When** the producer runs again over the same measured facts
- **Then** exit code is 0, stdout is empty, and the outbox is byte-identical to the first run's
- **Test:** `tests/test_orchestrator_tick.py::test_a_second_pass_over_unchanged_state_is_silent_and_the_outbox_is_byte_identical`

#### Scenario: a different clock is not a different fact

- **Given** a fact already emitted and acknowledged
- **When** the producer runs again with a different `--now`
- **Then** nothing is emitted, because the key carries the fact and not the time
- **Test:** `tests/test_orchestrator_tick.py::test_the_delta_key_is_the_fact_set_never_the_run_time`

### Requirement: recovery reads and reports are first-class commands

`pending` MUST print the lines the outbox still holds undelivered — the exact bytes a lost delivery
would have carried, after the live-state filter — and MUST acknowledge nothing. `report` MUST print
the record, pending, acknowledged and suppressed counts and exit 0.

#### Scenario: pending recovers a lost delivery without consuming it

- **Given** an outbox holding one unacknowledged record
- **When** `pending` runs twice
- **Then** both runs print the same line and the outbox still holds it unacknowledged
- **Test:** `tests/test_orchestrator_tick.py::test_pending_prints_without_acknowledging`

#### Scenario: report counts the outbox without emitting

- **Given** one acknowledged and one suppressed record
- **When** `report` runs
- **Then** it prints the counts and exits 0, and stdout carries no dispatch line
- **Test:** `tests/test_orchestrator_tick.py::test_report_counts_the_outbox_without_emitting`
