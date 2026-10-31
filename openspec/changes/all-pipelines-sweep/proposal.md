# all-pipelines-sweep — one weekly pipeline that exercises every pipeline, and an audit of which make targets nothing runs

## Why

There is **no single pipeline that exercises every pipeline**. Measured at `main@29066371` (methods: `gh api
repos/asimov-agent/llgenie/actions/workflows`, `make -qp`):

- 26 workflows in the tree; 16 are `disabled_manually` and invisible from a green board —
  `registry-sync` disabled froze the engine registry for ~56 h (#1092); `security-scan` disabled left #781
  unprovable for ~58 h.
- `make -qp` → 304 targets (13 `_`-prefixed internal); only a small fraction are named by any workflow step.
  Nobody knows which targets nothing covers.

A weekly sweep that **names** what is disabled and what is red is the cheapest guard against a fleet silently
shrinking.

## What Changes

- **`.github/workflows/all-pipelines.yml`** — `workflow_dispatch` + a **weekly** `schedule` (Saturday 04:27
  UTC, its own odd minute — never a busy slot, issue #275; never `pull_request`, so it cannot double every
  PR's CI). It dispatches every dispatchable workflow **except itself** (dispatching every dispatchable
  workflow must not dispatch the umbrella or it recurses), awaits each dispatched run's verdict (not `gh
  workflow run` exit 0), and prints a table `workflow · dispatched run id · status/conclusion · completed_at`
  + a summary line `N ok · M failed · K disabled`.
- **Disabled reporting (acceptance #2):** a workflow whose live state is not `active` is shown as
  `DISABLED (owner re-enable required)`, excluded from ok/failed counts, and the excluded list is printed.
- **`make targets-coverage`** — lists every Makefile target with the callers found (workflow step, script
  reference, or none), distinguishing internal (`_`-prefixed) from user-facing targets, so "which targets
  does nothing run" becomes a measurement. Driven by `scripts/targets_coverage.py` (the dispatch table's
  sibling audit).
- **The weekly job states the sha it swept** (acceptance #4): a green is a fact about a tree, not a date.
- Both live behind the existing gates (`check-workflows`, `ci-lint`, `check-wiring`, `check-dispatch-forms`,
  `check-docs`, `ci-unit`), and the umbrella's table logic is covered by a test that asserts the disabled
  list appears (acceptance #5).

## Impact

- New files: `.github/workflows/all-pipelines.yml`, `scripts/all_pipelines.py`, `scripts/targets_coverage.py`,
  `tests/test_all_pipelines.py`, `tests/test_targets_coverage.py`.
- Makefile: `all-pipelines-sweep` + `targets-coverage` targets (new `.PHONY` entries).
- Regenerated docs/BOTS.md dispatch table + a BOTS paragraph; agent-wiki note + CHANGES.md row.

## Not covered

- Re-enabling one of the disabled workflows is an owner decision, per workflow (the sweep reports `DISABLED`, it
  does not re-enable).
- A target with no caller is reported, not deleted: deleting or documenting it is per-target follow-up.
