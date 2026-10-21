# Tasks — unit-gate-hermetic (issue #438)

- [ ] 1. OpenSpec change: `proposal.md`, `specs/unit-gate-hermetic/spec.md`, this checklist
- [ ] 2. `tests/fixtures/unit-suite.json`: the two live-Hub node ids are de-selected, each with a reason naming `make test-hub-live`
- [ ] 3. `Makefile`: `test-hub-live` runs exactly those node ids, `.PHONY`, `##` help line
- [ ] 4. `tests/test_hub_live_target.py`: the gate's de-selection, the target's nodes + phony, every de-selection naming a test that still exists, and the two node ids still defined
- [ ] 5. `README.md` + `agent-wiki/2026-10-21-unit-gate-hermetic.md` record the hermetic rule and the target
- [ ] 6. Verified: `make test-unit` green with **no `Timeout (`** line in its log, `make test-hub-live` green for real (network + the GGUF download), `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=unit-gate-hermetic` green
