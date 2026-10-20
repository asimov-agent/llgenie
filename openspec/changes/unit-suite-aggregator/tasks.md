# Tasks

- [ ] 1. `scripts/unit_tests.py` — the ONE aggregator of the hermetic unit suite: discovery of `tests/test_*.py` minus the roster, plus `list` / `argv` / `check` / `run`, stdlib only (it runs inside the test image)
- [ ] 2. `tests/fixtures/unit-suite.json` — the 15 deliberate exclusions (reason, issue, date, the target that runs each instead) and the 3 node-id deselections of the live TensorFold release reads
- [ ] 3. Makefile: `test-unit` runs `python scripts/unit_tests.py run` — the recipe names no test file at all; `make test-engine-bump-live` keeps the deselected live cases
- [ ] 4. `scripts/check_wiring.py` — a document the aggregator selects is wired through the target that runs it, the roster's consistency findings join the graph, and `make wiring-report` shows the seam
- [ ] 5. `tests/test_unit_suite.py` — the spec's scenarios against the real tree and real scratch trees: discovery, the roster's staleness in every direction, the node-id invocation, `run` refusing to start on a broken roster
- [ ] 6. The 7 self-wiring assertions (`test_agent_nerve.py:677`, `test_check_docs.py:233`, `test_engine_bump.py:1872`/`:1904`, `test_engine_skill_gap.py:549`, `test_issue_implementer.py:229`, `test_secret_output.py:308`, `test_wiring.py:230`) read the aggregator's selection instead of the recipe line
- [ ] 7. `AGENTS.md` states the rule: the unit suite is aggregated, never enumerated — a new `tests/test_*.py` needs no Makefile edit, an exclusion is a dated decision
- [ ] 8. `README.md` documents the seam, the roster file and the report command; `agent-wiki/` records the change, referencing issue #393 and the PR
- [ ] 9. Verified in `llgenie/test:latest`: `make test-unit` green with the discovered suite, `make check-wiring` exit 0, `make wiring-report` names the seam; on the host `make lint` and `make openspec-validate NAME=unit-suite-aggregator` exit 0
