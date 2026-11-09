# 2026-11-09 the maintenance step jobs are never unbounded (#2291, #1865 blanket)

The four **step** jobs of the three scheduled engine/registry maintenance workflows carried no
`timeout-minutes` (measured at `main@5c7f4020`, 2026-11-09): `engine-bump.yml::plan` and `::bump`,
`engine-bump-rebase.yml::rebase`, `registry-sync.yml::sync`. A hung one inherited GitHub's
**360-minute default** — invisible for six hours — while blocking the workflow's `concurrency` slot
and the live PR it renders. The #1865 standing rule ("a step never runs unbounded") had a blank in
its maintenance form: the existing guards pin only the engine-build workflows
(`test_engine_build_timeouts.py`) and `ci.yml`/`pipeline.yml` (`test_pipeline_timeouts.py`).

The change is two halves, landing together:

- **Bounds on the four step jobs** — `plan`/`rebase` `timeout-minutes: 30`, `bump`/`sync`
  `timeout-minutes: 120`. Each is a wide hang-detector, not a budget (the `#846` 5..300 band).
- **A general every-step-job guard** — new `tests/test_maintenance_workflow_timeouts.py` (auto-
  discovered by `make test-unit`) asserts every non-`uses` job in the three maintenance workflows
  declares a `timeout-minutes` in `5..300`, so a dropped bound OR a newly added unbounded job reds
  the suite. `test_engine_build_timeouts.py` / `test_pipeline_timeouts.py` are untouched.

Guard-proven on the PR head, all four job-miss variants independently: planted-missing
`timeout-minutes` reds (`AssertionError: maintenance step jobs missing a \`timeout-minutes\`
(#1865: a step never runs unbounded, #2291): ['registry-sync.yml::sync']`), restored → green
(`2 passed`). `make test-unit`/`check-workflows`/`check-wiring`/`check-docs`/`lint` green.
