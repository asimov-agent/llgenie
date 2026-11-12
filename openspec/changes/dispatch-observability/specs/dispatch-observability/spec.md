# Spec Delta — dispatch-observability (#2578)

## ADDED Requirements

### Requirement: liveness dispatches name their producer run

Every `engine-build` run dispatched by the registry-liveness workflow SHALL carry the
registry-liveness run id in its `producer_run` dispatch input, on both dispatch shapes (the
#2579 coalesced sweep and the #2567 single-cell dispatch), and `engine-build` SHALL echo that
input into the run's own log AND its step summary from the guard job — attribution without
correlating timestamps.

#### Scenario: a liveness-fired producer run is attributable in one lookup

- **Given** a registry-liveness run that dispatches engine-build (sweep or single-cell shape)
- **When** the producer run starts
- **Then** the dispatch carried `-f producer_run="<the liveness run id>"`, and the producer's
  guard job prints `dispatched_by_run=<run id>` and writes the producing run id into its
  step summary

### Requirement: an unattributed dispatch says so

When `engine-build` is dispatched with no `producer_run` (a human re-drive or the PR-lane
trigger), the provenance step SHALL record `dispatched_by_run=none-recorded` together with the
triggering actor, so an unattributed dispatch is visible as such rather than silent.

#### Scenario: a manual dispatch names its actor instead

- **Given** an `engine-build` workflow_dispatch with `producer_run` left empty
- **When** the guard job's provenance step runs
- **Then** the log and step summary show `dispatched_by_run=none-recorded` and the triggering
  actor

### Requirement: the dispatch wiring is text-locked

A hermetic unit test SHALL read both workflows and fail when a liveness dispatch no longer
passes `producer_run` or `engine-build` no longer echoes it.

#### Scenario: removing the wiring reddens the suite

- **Given** an edit that drops `-f producer_run=` from either dispatch shape, or drops the
  provenance step / the `producer_run` input from `engine-build.yml`
- **When** the hermetic unit suite runs
- **Then** `tests/test_check_engine_pins_published.py` fails, naming issue #2578
