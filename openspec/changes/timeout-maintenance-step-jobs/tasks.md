# timeout-maintenance-step-jobs — tasks

## Specification Tasks

**Requirement: every maintenance step job declares a maximum runtime**

- [x] `.github/workflows/engine-bump.yml`: `plan` `timeout-minutes: 30`, `bump` `timeout-minutes: 120`.
- [x] `.github/workflows/engine-bump-rebase.yml`: `rebase` `timeout-minutes: 30`.
- [x] `.github/workflows/registry-sync.yml`: `sync` `timeout-minutes: 120`.
- [x] New guard `tests/test_maintenance_workflow_timeouts.py` asserts every non-`uses` job in the
      three maintenance workflows declares a `timeout-minutes` in `5..300` (guard-proven: red on a
      planted-missing bound, green on the fixed tree).

**Requirement: the maintenance workflows are covered by a timeout-bounds gate**

- [x] The guard is a general every-step-job rule (not a narrower job list break of
      `test_engine_build_timeouts.py`); `test_engine_build_timeouts.py` and
      `test_pipeline_timeouts.py` are untouched.
- [x] Change-note trio (agent-wiki note + docs/changes.d fragment + regenerated CHANGES.md), per #1123.

## Acceptance Tasks

- [x] `make test-unit` (new guard file discovered and green), `make check-workflows`, `make check-wiring`,
      `make check-docs`, `make lint` all green on the PR.
- [x] Regression control proven both ways on the PR head: planted-missing `timeout-minutes` → red
      naming the job; restored → green (numbers recorded in pr-body.md).
