# engine-build-stall-holder

## ADDED Requirements

### Requirement: a stalled push run's FAIL line names the concurrency-group holder

When `engine_build_trigger.py` dispatches a `push=true` engine-build run and, at its deadline, the
awaited run is still `pending`/`queued` with zero jobs (blocked behind the global
`engine-build-push` concurrency group), the FAIL line MUST name the in-progress push-group holder,
flag the run **STALLED**, and state that a re-dispatch queues behind the same gate — it MUST NOT be
a bare `concluded queued/None`.

WHEN a `push=true` dispatch's awaited run has not materialised a job by the deadline AND an in-progress
`engine-build` push run holds the group
THEN the FAIL line includes `STALLED behind engine-build-push group holder run <id>` and the words
`re-dispatch queues behind the same gate`, never a bare `concluded queued/None`.

#### Scenario: a held run names its push-group holder

- **Given** a `push=true` dispatch whose awaited run stays `pending` (0 jobs) and an in-progress push run `5` holds `engine-build-push`
- **When** the trigger reaches its deadline poll
- **Then** the FAIL line names `holder run 5`, flags **STALLED**, and warns that a re-dispatch queues behind the same gate
- **Test:** `tests/test_engine_build_trigger.py::test_stalled_behind_push_holder_is_named_not_a_bare_queued`
  drives a fake `gh` whose new run stays `pending` and yields holder `5`; asserts `STALLED behind engine-build-push group holder run 5` and the re-dispatch warning on stderr, with the bare `concluded pending/None` facts still present

### Requirement: a pending run without a holder stays a plain failure

When the awaited run is still `pending`/`queued` at deadline but NO in-progress `engine-build` push run
exists (the gate is free, so the stall is not attributable to a holder), the FAIL line MUST remain the
plain `concluded <status>/<conclusion>` fact with no **STALLED** suffix invented.

WHEN the awaited run is `pending` at deadline and no in-progress push run holds the group
THEN the FAIL line is the plain `concluded pending/None` fact, with no holder named and no **STALLED** suffix.

#### Scenario: no holder means no false STALLED attribution

- **Given** a `push=true` dispatch whose awaited run stays `pending` and the run list contains no in-progress `engine-build` push run
- **When** the trigger reaches its deadline poll
- **Then** the FAIL line is the plain `concluded pending/None` fact and does not name any holder
- **Test:** `tests/test_engine_build_trigger.py::test_stalled_without_holder_is_a_plain_failure`
  drives a `pending` run with `stall_holder=None` and asserts `STALLED behind` is absent while `concluded pending/None` is present
