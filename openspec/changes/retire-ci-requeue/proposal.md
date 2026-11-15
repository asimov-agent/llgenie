# Retire the ci-requeue re-rerun lane (issue #2702)

## Why

The owner's CI-discipline policy (issue #2701) says the agent must NEVER start a CI pipeline
manually: no `gh run rerun`, no `gh workflow run`, no requeue loops. Only GitHub events
(push/PR) and the weekly engine-bump / engine-image / latest-models+inference-servers lane start
pipelines. `scripts/ci_requeue.py` + `.github/workflows/ci-requeue.yml` + `make ci-requeue-cancelled`
are a scheduled requeue loop: a cron `gh run rerun` machine. It directly contradicts the policy and
was already deactivated on `main` by the ci-discipline-gate change (issue #2701) — its `schedule:`
block was deleted, leaving a dead lane whose target any human could still fire with a `gh` call.

## What Changes

- DELETE `scripts/ci_requeue.py`, `.github/workflows/ci-requeue.yml`, `tests/test_ci_requeue.py`.
- DELETE the `ci-requeue-cancelled` make target (`mk/ci.mk`, Makefile `.PHONY` roster).
- REMOVE the lane from every repo mechanism that could reach it: `run_failure_reactor.py`
  PIPELINE_STEMS + its cancelled-run message (now names the human-UI rerun rule), `fix_bot_sweep.py`
  pending-cancel message, `zero-job-pending.yml`'s `workflow_run` roster (re-pointed to
  `ci-frozen-reaper`, the allow-listed sweeper), header comments in `ci_frozen_reaper.py`,
  `ci_verdict.py`, `all_pipelines.py`, `bots_restore_health.py`, `check_workflows.py`,
  `ci-frozen-reaper.yml`, `ci-hf-live.yml`.
- REMOVE the lane from inventories: `scripts/package-layers.json`,
  `tests/fixtures/import-roots-baseline.json`.
- DOCS: drop the lane row/target/paragraph from `docs/BOTS.md` (replaced by a retirement note),
  drop it from `docs/ARCHITECTURE.md`'s monitor/script lists; `docs/changes.d/` fragment +
  `agent-wiki/` entry.
- A rerun of a CI run is now ONLY a human GitHub-UI action; no repo mechanism re-runs a pipeline.

## Out of scope (separate issues per policy)

- Re-homing the retired monitors' coverage (`zero-job-pending`'s long-term home) is already handled
  by the re-point to `ci-frozen-reaper` here; a deeper re-home review is issue #2703's lane.
