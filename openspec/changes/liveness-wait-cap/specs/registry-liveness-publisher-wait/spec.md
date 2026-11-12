# registry-liveness-publisher-wait — spec delta (liveness-wait-cap)

## MODIFIED Requirements

### Requirement: a liveness run waits for the same-head publisher run before the manifest gate

`registry-liveness` MUST, before any GHCR manifest check, poll for the `ci.yml` run at the same
head SHA on **every trigger event** — that run is the publisher of the pins in this tree, and a
scheduled or rerun liveness can land inside its publish window just like a push can. The wait is
bounded by a **wall-clock budget the script itself enforces**: the poll loop tests elapsed seconds
against a deadline comfortably below the step timeout, so the bound always expires through the
`publisher_still_running` defer path and never by a step timeout cancelling the loop before the
deferral is recorded. A run whose head has no same-head publisher (the normal scheduled case)
proceeds to the manifest gate after a short registration-grace poll instead of waiting blindly.
If the publisher is still running when the budget expires, the run must NOT hard-fail the fleet
gate (the tag is mid-publish, not missing) and must defer the verdict to a non-racing run.

WHEN `registry-liveness` runs (any `github.event_name`)
THEN it records the `ci.yml` run id at the same head SHA, polls until that run concludes, the
budget expires, or a bounded grace proves no same-head publisher exists, and passes the publisher's
state (`concluded success` / `concluded failure` / `in flight` / `none`) to the fleet gate.

#### Scenario: a run that races a still-running publisher does not hard-fail

- **Given** a liveness run whose same-head publisher has NOT concluded within the wait budget
- **When** the fleet gate would otherwise see a committed pin's tag unresolved
- **Then** the run records "publisher still in flight" and exits green (non-zero exit suppressed),
  because the tag is being published, not missing
- **Test:** `tests/test_check_engine_pins_published.py::test_publisher_still_in_flight_does_not_hard_fail`

#### Scenario: the bound is a wall-clock budget smaller than the step timeout

- **Given** the publisher-wait step's `timeout-minutes`, its poll interval, and its budget
- **When** the workflow is inspected
- **Then** the loop bounds itself with an elapsed-time deadline strictly smaller than the step
  timeout, and the budget exceeds the measured worst-case publisher runtime (40 m 21 s), so a slow
  publisher defers instead of cancelling the step mid-loop
- **Test:** `tests/test_check_engine_pins_published.py::test_publisher_wait_budget_always_expires_before_its_step_timeout`

#### Scenario: the wait runs on every trigger event, not only push

- **Given** the publisher-wait step in `registry-liveness.yml`
- **When** the workflow is inspected
- **Then** the step carries no `github.event_name == 'push'` gate, and a head with no matching
  same-head publisher exits the poll after the bounded registration grace
- **Test:** `tests/test_check_engine_pins_published.py::test_publisher_wait_runs_for_every_trigger_event`

#### Scenario: a wait that hits its budget is never a silent green

- **Given** a liveness run whose same-head publisher is still in flight when the budget expires
- **When** the step finishes
- **Then** the run carries a `::warning::` annotation naming the deferral (budget, head SHA, and
  "this run verified nothing") beside the `publisher_still_running` job output, so a deferred run
  is distinguishable from a verified-green run at a glance
- **Test:** `tests/test_check_engine_pins_published.py::test_publisher_wait_budget_always_expires_before_its_step_timeout`

### Requirement: a sweep is dispatched only when the same-head publisher succeeded

A liveness run MUST NOT dispatch an engine-build sweep for a SHA whose own `ci.yml` publisher run
concluded failure — dispatching a sweep that reproduces the publisher's own known failure just files
a second red run (measured: sweeps #682/#684 failed `vllm-rocm ... Permission denied` at `85be1b6a87`,
fixed only in `b32594c8c4`). This holds on every trigger event, since the publisher poll now runs for
scheduled and rerun liveness too. When the publisher failed, the tracking issue names the failed
publisher run instead, and the hard-fail is determined by the actual manifest state.

WHEN a run's same-head publisher concludes `failure` with one or more pins unpublished
THEN the run files the tracking issue naming the failed publisher run and does NOT call
`gh workflow run engine-build.yml` (the `[select]`-derived dispatch is suppressed); the fleet gate's
hard-fail still reflects the real manifest state.

#### Scenario: the publisher failed, so no sweep is dispatched and the issue names the run

- **Given** a liveness run whose same-head publisher concluded `failure` and a pin that is still unpublished
- **Then** the dispatch step exits without starting `engine-build`, and the tracking issue's body names
  the failed publisher run id
- **Test:** `tests/test_check_engine_pins_published.py::test_no_sweep_dispatched_for_a_failed_publisher`

#### Scenario: the publisher succeeded, the dispatch contract is unchanged

- **Given** a liveness run whose same-head publisher concluded `success` and a pin that is still unpublished
- **Then** the run files the tracking issue, dispatches `engine-build` per the `[select]` contract, and
  the fleet gate's `exit "$rc"` hard-fail stays in force
- **Test:** `tests/test_check_engine_pins_published.py::test_scheduled_and_successful_publisher_keep_the_dispatch_contract`
