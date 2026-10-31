# all-pipelines sweep — one weekly pipeline exercises every pipeline, and targets-coverage audits who calls what (issue #1102)

Delivered as the `all-pipelines-sweep` change. There was no single pipeline that triggered all the others, and
16 of 26 workflows were `disabled_manually`, invisible from a green board; `make -qp` said 304 targets but
nobody knew which targets nothing ran.

## What was verified

- **Umbrella (`.github/workflows/all-pipelines.yml`)** — `workflow_dispatch` + weekly `schedule` Saturday
  04:27 UTC (issue #275's own-odd-minute). The `sweep` job runs `make all-pipelines-sweep REPO=<owner>/<repo>`
  (`scripts/all_pipelines.py`): enumerates the tree's workflows, classifies each active/disabled via the API,
  dispatches every dispatchable workflow **except itself** (no recursion), awaits each dispatched run's own
  `status/conclusion/completed_at`, and renders `workflow · dispatched run id · status/conclusion · completed_at`
  + `N ok · M failed · K disabled`.
- **Disabled reporting** — a non-active workflow renders `DISABLED (owner re-enable required)`, is excluded
  from ok/failed, and is named in the printed excluded list — a green summary can never hide dead pipelines.
- **Failure isolation** — one red pipeline never aborts the sweep: the full table is printed and the job fails
  at the end iff any non-disabled run failed. `concurrency.cancel-in-progress: false` (the sweep never cancels).
- **Sha stated** — the report names the sha it swept (a green is a fact about a tree, not a date).
- **`make targets-coverage`** — `scripts/targets_coverage.py` projects `make -qp` targets against the callers
  found (workflow step, script reference, or none), marking `_`-prefixed targets internal. Measured at
  `main@29066371`: 304 targets, 13 internal, 60 user-facing with no caller.
- **Gates** — the new workflow passes `check-workflows` (the run-failure reactor's `workflow_run` roster has a
  dated exemption: the umbrella's red IS the report, and the failed pipeline's own completion already routes to
  the reactor), `check-dispatch-forms` (header block + regenerated docs/BOTS.md table), `check-wiring` (both new
  scripts wired to `.PHONY` targets), `check-docs` (BOTS paragraph + note + fragment), and `ci-lint`.
- **Regression lock (acceptance #5)** — `tests/test_all_pipelines.py::test_a_disabled_workflow_is_reported_and_excluded`
  fails when a disabled workflow is treated as green (proved the gate catches the bug by mutation, then restored).

## Decision

The umbrella does not dispatch itself — "dispatch every dispatchable workflow" excludes `all-pipelines.yml`,
or the weekly sweep would recurse. Re-enabling one of the disabled workflows is an owner decision, per
workflow; the sweep reports `DISABLED`, it does not re-enable.

## Refs

Issue: #1102 · PR: #__PR__
