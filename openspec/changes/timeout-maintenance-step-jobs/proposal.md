# timeout-maintenance-step-jobs — proposal

Issue: [#2291](https://github.com/asimov-agent/llgenie/issues/2291)

## Why

The **step** jobs of the three scheduled engine/registry maintenance workflows carry no
`timeout-minutes`, so a hung one inherits GitHub's **360-minute default** — invisible for six hours:

| workflow | job | why a hang is the failure mode |
|---|---|---|
| `engine-bump.yml` | `plan` | `git ls-remote` + plan across every engine skill |
| `engine-bump.yml` | `bump` | pin + derive + apply + the live TensorFold archive proof (`make test-engine-bump-live`) |
| `engine-bump-rebase.yml` | `rebase` | forward-merges every open engine-bump PR onto `main` and force-pushes |
| `registry-sync.yml` | `sync` | sync + render + `make test-unit` (11 steps) |

No existing gate covers them: `tests/test_engine_build_timeouts.py` pins only the engine-build
workflows and `tests/test_pipeline_timeouts.py` pins `ci.yml`/`pipeline.yml`. A future edit that
drops a bound (or adds a new unbounded job to one of these three) lands green. And because these
workflows each render a live GitHub PR behind a `concurrency` group, a zombie run blocks the whole
weekly/daily slot — the #1865 standing rule has a blank in its maintenance form.

## What Changes

- **`.github/workflows/engine-bump.yml`**: `plan` gets `timeout-minutes: 30`, `bump` gets
  `timeout-minutes: 120`.
- **`.github/workflows/engine-bump-rebase.yml`**: `rebase` gets `timeout-minutes: 30`.
- **`.github/workflows/registry-sync.yml`**: `sync` gets `timeout-minutes: 120`.
- **`tests/test_maintenance_workflow_timeouts.py`** (new, auto-discovered by `make test-unit`): a
  general every-step-job-bound rule — every non-`uses` job in the three maintenance workflows must
  declare a `timeout-minutes` in the `5..300` hang-ceiling band, so a dropped bound OR a newly
  added unbounded job reds the suite.
- Change-note trio: `agent-wiki/2026-11-09-timeout-maintenance-step-jobs.md` +
  `docs/changes.d/2026-11-09-timeout-maintenance-step-jobs.md` + a `CHANGES.md` row.

Bounds only — no step, gate or secret is weakened; ceilings are wide hang-detectors, not budgets.

## Benefit

A hung engine-bump/rebase/registry-sync step becomes a loud `timeout` naming its run/job instead of
a silent 360-minute block on the schedule slot and the PR it edits; future edits to the maintenance
workflows can no longer reintroduce the unbounded default without reddening a gate. The maintenance
workload surfaces the same guard the engine-build and pipeline paths already have (#1865 blanket).
