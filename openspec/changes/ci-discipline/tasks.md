# Tasks

- [ ] 1. Remove the `on.schedule:` trigger block from the eight deactivated lanes (architecture-bot, ci-requeue, issue-bot, issue-dedupe, issue-refiner, registry-sync-review, search-smoke, rebase-bot), keeping every other trigger — and update each file's `Trigger surface` comment to note the schedule is removed
- [ ] 2. `scripts/check_ci_discipline.py`: a hermetic, stdlib-only gate with `check` / `report` commands, failing when (a) a `schedule:` key appears outside the 18-file allow-list, (b) an allow-listed file loses its schedule, (c) an allow-listed schedule declares no `- cron:`, (d) `ci.yml`/`pipeline.yml` carry an agent-leg or agent-image job, (e) an agent-leg-using workflow is outside the agent-leg allow-list, (f) AGENTS.md lacks the durable CI-discipline section
- [ ] 3. Makefile: `check-ci-discipline` target in `mk/ci.mk` (with a `##` help line) + `.PHONY`, wired into the `ci-unit` sequence
- [ ] 4. `scripts/issue_bot_gates.py`: classify `check-ci-discipline` in `FAST_GATES` (or DEFFERED with reason) so `ci-unit`'s roster check stays green
- [ ] 5. `scripts/package-layers.json`: register `check_ci_discipline` in Structural gates
- [ ] 6. `tests/test_ci_discipline.py`: fixture-copy-tree tests for each failure direction (schedule add to non-allowlisted, allowlist lose schedule, agent job in ci.yml, agent leg outside allowlist, missing AGENTS section, schedule-no-cron) and a real-tree pass
- [ ] 7. AGENTS.md: add the durable CI-discipline section (weekly engine/registry lane only; main pipeline tests-only; Hermes only in agent-image engine/registry legs; agent never starts CI manually)
- [ ] 8. Wiki: `agent-wiki/2026-11-15-ci-discipline-2702.md` + `docs/changes.d/2026-11-15-ci-discipline-2702.md` fragment + regenerated `CHANGES.md` index row
- [ ] 9. OpenSpec: `make openspec-validate NAME=ci-discipline` and `make openspec-tasks-check` pass (task list must be fully ticked before done)
- [ ] 10. Verification: `make lint`, `make test-unit`, `make check-wiring`, `make check-docs`, `make check-workflows`, `make check-issue-bodies`, `make openspec-tasks-check` all green
