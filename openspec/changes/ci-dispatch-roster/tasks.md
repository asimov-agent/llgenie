# Tasks: ci-dispatch-roster

- [x] 1. `AGENTS.md`: rewrite the "The agent never manually starts a CI pipeline" bullet into the dispatch-roster wording (owner / collaborator / GitHub itself may dispatch; `gh run rerun` and requeue loops stay forbidden for the agent)
- [x] 2. `scripts/check_ci_discipline.py`: `AGENTS_PIN_PHRASES` pins the roster + the queue-pumping ban instead of the blanket-ban phrase
- [x] 3. `tests/test_ci_discipline.py`: keep/extend the pin test so a roster-less AGENTS.md is a finding
- [x] 4. Docs: `docs/changes.d` fragment + `agent-wiki` entry naming #2718 and the PR
- [x] 5. Gates green on the branch: `make check-ci-discipline check-workflows check-wiring check-docs openspec-validate lane-preflight test-unit`
- [x] 6. (#2721) `AGENTS.md`: the bullet states the agent's local-`make` verification mode, the starters (human / cron lane / GitHub events incl. PR creation and merge), and the failing-workflow-testing exception
- [x] 7. (#2721) `scripts/check_ci_discipline.py` pins "verifies locally with `make`" + "test a workflow that is failing"; `tests/test_ci_discipline.py` proves both directions green/finding
- [x] 8. (#2721) Docs: changes.d fragment update + agent-wiki entry naming #2721 and the PR; gates re-green on the new head
