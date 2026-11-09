# run-reactor-engine-acceptance-dispatch-form

## ADDED Requirements

### Requirement: an engine-build acceptance criterion names the dispatch run, never a local build

The run-failure reactor's `issue_body` MUST render a failing `engine-build` cell's acceptance
criterion 1 in the provable dispatch form — "green in a real run of the failing cell, with its own
log recorded" — and MUST never render "green locally on this host" for an ENGINE-lane failure,
because this repository forbids building an inference-server engine image locally (AGENTS.md
"Inference servers run ONLY in their container images"; `agents/llgenie-engine-improver/SOUL.md`
"Never build an inference-server engine image locally").

WHEN the reactor files an issue for an `ENGINE_LANE` failure with no pushable PR
THEN the body's acceptance criterion names the real-run dispatch form and does not name a local build

#### Scenario: an engine-build failure names the real run, never a local build

- **Given** a failing `engine-build` run routed to the engine lane with no pushable PR
- **When** the reactor renders the issue body with `lane == ENGINE_LANE`
- **Then** acceptance criterion 1 reads "the failing cell is green in a real run of the failing
  cell, with its own log recorded" and the body does not contain "green locally on this host"
- **Test:** `tests/test_run_failure_reactor.py::test_an_engine_build_acceptance_names_the_dispatch_run_never_a_local_build`

## MODIFIED Requirements

### Requirement: the acceptance gate's finding for a locally-worded unticked criterion points at the dispatch form

The acceptance gate (`scripts/check_pr_acceptance.py`) MUST, when it reports an unticked criterion
whose wording names a local build, append the dispatch form so the implementer reads the correct
restatement in the gate's own output — never silently leaving the local-build wording as the remedy.

WHEN the gate reports an unticked criterion whose text names a local build
THEN its finding points at the dispatch-run form for an engine-build fix

#### Scenario: a locally-worded unticked criterion is re-stated as the dispatch form

- **Given** an engine-build criterion d in an unticked state whose text names a local build
- **When** the acceptance gate renders the finding
- **Then** the finding text carries the dispatch-run form ("green in a real run of the failing
  cell, with its own log recorded")
- **Test:** `tests/test_check_pr_acceptance.py::test_unticked_local_build_criterion_points_at_the_dispatch_form`
