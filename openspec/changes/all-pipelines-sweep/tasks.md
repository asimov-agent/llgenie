# Tasks — all-pipelines-sweep (issue #1102)

## The umbrella workflow

- [x] Add `.github/workflows/all-pipelines.yml`: `workflow_dispatch` + weekly `schedule` on an odd minute
      (Saturday 04:27 UTC, its own slot, never `pull_request`), that runs `make all-pipelines-sweep`.
- [x] The workflow file has the dispatch header block (`Trigger surface` / `Flow` / `Never`), a `name:` that
      states the work, and a documented dispatch form; `make check-dispatch-forms` passes.
- [ ] The workflow passes `make check-workflows` and `make ci-lint` (`${{ }}` parses, trailing newline).
- [ ] Regenerate the docs/BOTS.md `dispatch-forms` table with `make dispatch-forms-report` and paste between
      the markers; add a BOTS paragraph for the umbrella.

## The sweep script

- [x] Add `scripts/all_pipelines.py`: enumerate the tree's `.github/workflows/*.yml`, classify each as
      active/disabled via `gh api`, dispatch every dispatchable workflow except `all-pipelines.yml`, await
      each dispatched run's verdict (`status`/`conclusion`/`completed_at`), and render the table + summary.
- [x] Disabled workflows render as `DISABLED (owner re-enable required)`, excluded from ok/failed, named in a
      printed excluded list.
- [x] The report states the sha it swept.
- [x] Failure isolation: the full table is emitted and the process exits non-zero at the end if any non-disabled
      run failed; nothing is cancelled.
- [x] Wire `scripts/all_pipelines.py` through `make all-pipelines-sweep` (a new `.PHONY` target the workflow
      calls); `make check-wiring` passes.

## The targets-coverage audit

- [x] Add `scripts/targets_coverage.py`: project `make -qp` targets against the callers found in workflows and
      scripts, marking `_`-prefixed targets internal, and print each target with its callers or `none`.
- [x] Wire `make targets-coverage` (a new `.PHONY` target) to that script; `make check-wiring` passes.

## Tests (no mocks; the real projectors and fixture trees)

- [x] `tests/test_all_pipelines.py`: dispatches every dispatchable except itself + awaits; failure isolation
      fails at the end; states sha; disabled-reported-and-excluded; every disabled reported.
- [x] `tests/test_targets_coverage.py`: every target listed with caller or `none`; internal distinct; totals
      stated and reproducible.
- [x] Regenerate the disabled-list regression (acceptance #5) is locked by
      `test_a_disabled_workflow_is_reported_and_excluded`, which fails if a disabled workflow counts as `ok`.
- [x] Rule-6 proof: the disabled-list test fails when a disabled workflow is treated as green and passes once
      restored (verified locally, then reverted).

## Gates

- [x] `make check-dispatch-forms` GREEN, `make dispatch-forms-report` table current.
- [x] `make check-workflows`, `make ci-lint`, `make check-wiring`, `make check-docs` GREEN.
- [x] `make targets-coverage` runs and prints every target with callers or `none`.
- [ ] `make test-unit` GREEN (the new tests are selected by the unit-suite aggregator).
- [x] `make openspec-validate NAME=all-pipelines-sweep` GREEN, every task ticked.
- [ ] `make loop` GREEN (or `make test-unit` + `make openspec-validate` if the full hardware loop cannot run;
      report which).
- [ ] agent-wiki note + CHANGES.md row in the same commit; commit + push to the fork; PR against
      `asimov-agent/llgenie:main` from `andyholst:feat/1102-all-pipelines`, body ends `closes #1102`.
