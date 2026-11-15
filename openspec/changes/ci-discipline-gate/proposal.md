# Change: CI pipeline discipline — weekly engine/registry lane only, tests-only main pipeline, Hermes in agent-image lanes only

## Why

Issue #2701 (owner mandate 2026-11-15): the ONLY workflow allowed to run on a `schedule:` clock
besides the merge/dispatch housekeeping roster is the engine-bump + engine-image lane; the CI main
pipeline runs TESTS ONLY (no LLM/agent leg); Hermes calls in CI live only in agent-image lanes whose
purpose is fetching latest engine servers, registry sync, engine-list updates and Dockerfile updates;
and no repo mechanism may start a CI pipeline on a human's or agent's behalf beyond GitHub events.
Measured at `dcfb96b7df`: 8 bot lanes (architecture-bot, ci-requeue, issue-bot, issue-dedupe,
issue-refiner, registry-sync-review, search-smoke, rebase-bot) ran their agent legs on wall-clock
crons — agent work fanning out unattended — and nothing in the tree could tell when any of those
rules drifted.

## What Changes

- **Deactivated (clock removed, other triggers kept):** the 8 lanes above lose their
  `on.schedule:` blocks; `workflow_dispatch` / `repository_dispatch` / push/PR triggers stay.
- **4 tests re-homed:** `tests/test_ci_requeue.py`, `tests/test_architecture_bot.py`,
  `tests/test_agent_web_reach.py`, `tests/test_bot_pipeline_isolation.py` assert the new no-schedule
  shape instead of the old cron strings.
- **New gate `scripts/check_ci_discipline.py`** (`make check-ci-discipline`, `make
  ci-discipline-report`) enforcing four faces: the schedule allow-list (both directions — a new clock
  outside it, a stale allow-list entry), the tests-only main pipeline (`ci.yml`, `pipeline.yml`,
  `all-pipelines.yml` carry no agent marker), the agent-leg lane allow-list (engine/registry agent
  lanes + dispatch-only bot lanes + `publish-agent-image.yml` + `search-smoke.yml`), and the durable
  AGENTS.md section (header + pin phrases).
- **Wiring:** `mk/gates.mk` targets, `scripts/ci_unit.py` `MAKE_SEQUENCE` (post-#2705 home of the
  `ci-unit` chain; `tests/test_ci_unit_stage.py` documents the one addition since the base capture),
  `scripts/package-layers.json` CI group, `scripts/issue_bot_gates.py` DEFERRED roster.
- **AGENTS.md** gains the durable section "CI pipeline discipline: weekly engine/registry lane only,
  tests-only main pipeline, Hermes in agent-image lanes only (mandatory, durable)".

No workflow job bodies change: this removes clocks and adds a gate; retiring the `ci-requeue`
machinery itself is issue #2702, and re-homing the deactivated lanes' behaviour is #2703 — both stay
open after this change.

## Impact

- Affected specs: `ci-pipeline` (tests-only main pipeline, schedule allow-list)
- Affected code: 8 `.github/workflows/*.yml`, `AGENTS.md`, `mk/gates.mk`, `mk/ci.mk`,
  `scripts/check_ci_discipline.py` (new), `scripts/package-layers.json`, `scripts/issue_bot_gates.py`,
  `tests/test_ci_discipline.py` (new), 4 re-homed tests, `docs/changes.d/`, `agent-wiki/`
