# engine-build-trigger-cancelled

## ADDED Requirements

### Requirement: a cancelled/skipped producer is terminal — the trigger stops waiting and names the cause

When `_dispatch_and_wait` observes its awaited producer run with `conclusion` `cancelled` or
`skipped`, the wait MUST end immediately (not at the `wait_min` deadline) and `check` MUST print a
FAIL line naming the cause — `producer cancelled — nothing to wait for` / `producer skipped — nothing
to wait for` — with the run id. A concurrency-cancelled run may report `conclusion: cancelled` while
its `status` stays `in_progress`, so the terminal decision comes from the CONCLUSION, never from the
status field alone.

WHEN the awaited producer run reports `conclusion` of `cancelled` or `skipped`
THEN the trigger stops polling immediately and the FAIL line names the terminal cause with the run id.

#### Scenario: a cancelled producer terminates the wait with a named cause

- **Given** a `push=true` dispatch whose new run reports `status: in_progress, conclusion: cancelled`
- **When** the trigger awaits that run
- **Then** it returns immediately (not after `wait_min`) and emits `producer cancelled — nothing to wait for` on stderr
- **Test:** `tests/test_engine_build_trigger.py::test_cancelled_producer_terminates_with_named_cause`
  drives a fake `gh` whose new run is `in_progress/cancelled` with `--wait-min 120` and asserts the named
  cause on stderr and `rc == 1`

#### Scenario: a skipped producer is equally terminal

- **Given** a `push=true` dispatch whose new run reports `status: in_progress, conclusion: skipped`
- **When** the trigger awaits that run
- **Then** it terminates with `producer skipped — nothing to wait for` and `rc == 1`
- **Test:** `tests/test_engine_build_trigger.py::test_skipped_producer_terminates_with_named_cause`

### Requirement: the wall-clock bound fails naming the producer run and its last known status

When the awaited producer run has never reached a terminal verdict by the `wait_min` deadline
(`run.status` is not `completed` and `conclusion` is not a terminal value), the trigger MUST stop and
fail naming the producer run id and its last known status — `wait bound (<n> min) expired — producer
run <id> never concluded, last status <status>` — NEVER the bare `concluded <status>/<conclusion>`
line that read like a verdict that happened. A STALLED behind the `engine-build-push` group holder must
still name that holder.

WHEN the `wait_min` deadline passes and the awaited run has neither concluded nor been cancelled/skipped
THEN the FAIL line names the producer run id and its last known status (and the push-group holder, when one holds the gate).

#### Scenario: expiry names the run and its last status

- **Given** a `push=true` dispatch whose new run stays `status: in_progress, conclusion: None` and `--wait-min 0`
- **When** the trigger's deadline poll arrives
- **Then** the FAIL line is `wait bound (0 min) expired — producer run 77 never concluded, last status in_progress` and `rc == 1`
- **Test:** `tests/test_engine_build_trigger.py::test_wait_expiry_names_the_run_and_last_status`
  asserts the run id `77` and `last status in_progress` on stderr

#### Scenario: a pending run behind the push-group holder still names the holder at expiry

- **Given** a `pending` (0-jobs) run held behind in-progress push run `5` and `--wait-min 0`
- **When** the trigger's deadline poll arrives
- **Then** the FAIL line names the `engine-build-push` holder run `5` as STALLED along with the expiry facts
- **Test:** `tests/test_engine_build_trigger.py::test_stalled_behind_push_holder_is_named_not_a_bare_queued`
  (updated to the expiry message shape) asserts `STALLED behind engine-build-push group holder run 5`
  and `wait bound (0 min) expired` / `last status pending`

## MODIFIED Requirements

### Requirement: a pending run without a holder stays a plain failure — now as an explicit expiry

The prior "plain `concluded pending/None` fact" for a run that never concludes is replaced by the
explicit expiry line `wait bound (<n> min) expired — producer run <id> never concluded, last status
<pending>`, which still names no holder when none exists.

WHEN a `pending`/`queued` run reaches the deadline with no in-progress push-group holder
THEN the FAIL line is the expiry form naming the run and its `pending` status, with no STALLED suffix.

#### Scenario: no holder means no false STALLED attribution

- **Given** a `pending` run with no holder and `--wait-min 0`
- **When** the trigger's deadline poll arrives
- **Then** the FAIL line is the expiry form (`last status pending`) and names no holder
- **Test:** `tests/test_engine_build_trigger.py::test_stalled_without_holder_is_a_plain_failure`
  (updated to the expiry message shape) asserts `STALLED behind` is absent and `wait bound (0 min) expired` / `last status pending` are present
