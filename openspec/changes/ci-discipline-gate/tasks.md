# Tasks: ci-discipline-gate

## 1. Baseline
- [x] 1.1 Survey every workflow's triggers at the PR base: files declaring `on.schedule:`, their cron strings, and every file using a Hermes agent marker
- [x] 1.2 File the umbrella #2701 and the two linked lanes #2702/#2703 (bidirectional links in all three bodies)

## 2. Deactivation
- [x] 2.1 Remove the `schedule:` blocks from the 8 lanes (architecture-bot, ci-requeue, issue-bot, issue-dedupe, issue-refiner, registry-sync-review, search-smoke, rebase-bot); all other triggers unchanged
- [x] 2.2 Re-home the 4 tests that asserted the old cron strings (`test_ci_requeue.py`, `test_architecture_bot.py`, `test_agent_web_reach.py`, `test_bot_pipeline_isolation.py`) — no-schedule assertions replace cron assertions

## 3. The gate
- [x] 3.1 Write `scripts/check_ci_discipline.py`: schedule allow-list (both directions), tests-only main pipeline, agent-leg lane allow-list, AGENTS.md section+pin phrases; `check` exits 1 naming the offending file, `report` exits 0
- [x] 3.2 Hermetic tests `tests/test_ci_discipline.py`: green on the real tree, red against fixture trees for each failure direction (new clock outside the allow-list, allow-listed lane loses its clock, tests-only pipeline gains an agent job, deactivated lane re-schedules, AGENTS.md loses the section)
- [x] 3.3 Wire it: `mk/gates.mk` targets + `.PHONY`, `scripts/ci_unit.py` `MAKE_SEQUENCE` (+ `tests/test_ci_unit_stage.py` documented-addition seam), `scripts/package-layers.json` CI group, `scripts/issue_bot_gates.py` DEFERRED

## 4. Rules of record
- [x] 4.1 AGENTS.md gains the durable CI-discipline section (weekly engine/registry lane, tests-only main pipeline, Hermes only in agent-image engine/registry legs, agent never manually starts CI)
- [x] 4.2 `make check-ci-discipline` green on the tree; allow-list gap found and fixed in review (publish-agent-image, search-smoke) with rationale strings

## 5. Verification
- [x] 5.1 `make openspec-validate NAME=ci-discipline-gate` exits 0
- [x] 5.2 The targeted test modules (`test_ci_discipline.py`, the 4 re-homed tests, `test_check_cron_drift.py`, `test_all_pipelines.py`) pass together, and `make test-unit` is green including the gate's tests
- [x] 5.3 `make lane-preflight` prints `preflight: OK` on the pushed head
