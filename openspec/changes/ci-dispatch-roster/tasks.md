# Tasks: ci-dispatch-roster

- [x] 1. `AGENTS.md`: rewrite the "The agent never manually starts a CI pipeline" bullet into the dispatch-roster wording (owner / collaborator / GitHub itself may dispatch; `gh run rerun` and requeue loops stay forbidden for the agent)
- [x] 2. `scripts/check_ci_discipline.py`: `AGENTS_PIN_PHRASES` pins the roster + the queue-pumping ban instead of the blanket-ban phrase
- [x] 3. `tests/test_ci_discipline.py`: keep/extend the pin test so a roster-less AGENTS.md is a finding
- [x] 4. Docs: `docs/changes.d` fragment + `agent-wiki` entry naming #2718 and the PR
- [x] 5. Gates green on the branch: `make check-ci-discipline check-workflows check-wiring check-docs openspec-validate lane-preflight test-unit`
