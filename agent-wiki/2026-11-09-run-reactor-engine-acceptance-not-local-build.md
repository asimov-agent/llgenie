# The run-failure reactor's engine-build acceptance criterion names the dispatch run, never a local build (issue #2109)

## What changed

A failed `engine-build` cell can never be proved by a local build: AGENTS.md
"Inference servers run ONLY in their container images" and the engine lane's SOUL "Never
build an inference-server engine image locally" forbid building the image on the host. Yet
`scripts/run_failure_reactor.py`'s `issue_body` rendered the same forbidden criterion for an
engine-lane failure as for any other ("the failing make target is green locally on this host,
with its real output recorded"), so every engine-build failure issue was unclosable by the
book and the acceptance gate redded the engine lane's fix PR on a line no implementer is
allowed to satisfy.

`issue_body` now branches on the owning lane: an `ENGINE_LANE` failure's acceptance criterion 1
is the provable dispatch form — "the failing cell is green in a real run of the failing cell,
with its own log recorded", the single-cell `engine-build` dispatch that CI owns. `scripts/
check_pr_acceptance.py` carries the same remedy: when an unticked criterion names a local build
(`LOCAL_BUILD`), the `acceptance-unchecked` / `acceptance-proven-awaiting-writer` finding
appends the dispatch form so the implementer sees the right restatement in the log.

## Verification

`tests/test_run_failure_reactor.py::test_an_engine_build_acceptance_names_the_dispatch_run_never_a_local_build`
renders the engine-lane body and asserts criterion 1 is the dispatch form and that
"locally on this host" is absent; it FAILS against the pre-change reactor (stash-proven) and
PASSES on this branch. `tests/test_check_pr_acceptance.py::test_unticked_local_build_criterion_points_at_the_dispatch_form`
asserts the acceptance finding names the container rule and the dispatch form. Both modules:
75 passed.
