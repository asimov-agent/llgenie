# registry-liveness-publisher-wait — spec

## ADDED Requirements

### Requirement: a push-triggered liveness run waits for the same-head publisher run before the manifest gate

On a `push`-triggered run, `registry-liveness` MUST, before any GHCR manifest check, wait (bounded)
for the `ci.yml` run at the same head SHA to conclude — that run is the publisher of the pins in this
tree. The wait is bounded: if the publisher is still running when the bound expires, the run must NOT
hard-fail the fleet gate (the tag is mid-publish, not missing) and must defer the verdict to a
non-racing run.

WHEN `registry-liveness` is triggered by `github.event_name == 'push'`
THEN it records the `ci.yml` run id at the same head SHA, polls until that run concludes or the bound
expires, and passes the publisher's conclusion (`success` / `failure` / `in_flight`) to the fleet gate;
a `scheduled` run has no same-head publisher and keeps today's behaviour.

#### Scenario: a push-triggered run waits for the same-head CI run before the manifest check

- **Given** a `push` to `main` whose `ci.yml` run at the same head is still `in_progress`
- **When** liveness runs its fleet gate
- **Then** it polls the same-head `ci.yml` run (identified by head SHA) until that run concludes or the
  bound expires, and only a concluded run lets the manifest check decide
- **Test:** `tests/test_check_engine_pins_published.py::test_push_run_waits_for_the_same_head_publisher_before_the_manifest_check`

#### Scenario: a run that races a still-running publisher does not hard-fail

- **Given** a push-triggered liveness run whose same-head publisher has NOT concluded within the wait
  bound
- **When** the fleet gate would otherwise see a committed pin's tag unresolved
- **Then** the run records "publisher still in flight" and exits green (non-zero exit suppressed),
  because the tag is being published, not missing
- **Test:** `tests/test_check_engine_pins_published.py::test_publisher_still_in_flight_does_not_hard_fail`

### Requirement: a sweep is dispatched only when the same-head publisher succeeded

A push-triggered liveness run MUST NOT dispatch an engine-build sweep for a SHA whose own `ci.yml`
publisher run concluded failure — dispensing a sweep that reproduces the publisher's own known failure
just files a second red run (measured: sweeps #682/#684 failed `vllm-rocm ... Permission denied` at
`85be1b6a87`, fixed only in `b32594c8c4`). When the publisher failed, the tracking issue names the
failed publisher run instead, and the hard-fail is determined by the actual manifest state.

WHEN a push-triggered run's same-head publisher concludes `failure` with one or more pins unpublished
THEN the run files the tracking issue naming the failed publisher run and does NOT call
`gh workflow run engine-build.yml` (the `[select]`-derived dispatch is suppressed); the fleet gate's
hard-fail still reflects the real manifest state.

#### Scenario: the publisher failed, so no sweep is dispatched and the issue names the run

- **Given** a push-triggered liveness run whose same-head publisher concluded `failure` and a pin that
  is still unpublished
- **Then** the dispatch step exits without starting `engine-build`, and the tracking issue's body names
  the failed publisher run id
- **Test:** `tests/test_check_engine_pins_published.py::test_no_sweep_dispatched_for_a_failed_publisher`

#### Scenario: the publisher succeeded, the dispatch contract is unchanged

- **Given** a push-triggered liveness run whose same-head publisher concluded `success` and a pin that
  is still unpublished
- **Then** the run files the tracking issue, dispatches `engine-build` per the `[select]` contract, and
  hard-fails the job — today's `#2259` semantics preserved
- **Test:** `tests/test_check_engine_pins_published.py::test_the_liveness_workflow_dispatches_the_publish_not_just_names_it`
  and `test_the_dispatch_coalesces_a_multi_cell_wave_into_one_sweep` (unchanged)

#### Scenario: a scheduled run has no same-head publisher and keeps today's behaviour

- **Given** a `scheduled` (cron) `registry-liveness` run — no concurrent same-head publisher exists
- **Then** the run does not wait and keeps the file-issue + dispatch + hard-fail contract verbatim
- **Test:** `tests/test_check_engine_pins_published.py::test_the_liveness_workflow_hard_fails_on_a_committed_manifest_unknown`
  (unchanged)
