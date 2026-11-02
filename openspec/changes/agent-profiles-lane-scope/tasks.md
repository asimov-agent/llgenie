# agent-profiles-lane-scope

- [x] `scripts/check_agent_profiles.py`: `--profile NAME` (validated, unknown exits 2) filters findings to `_profile_of(where) in (None, NAME)`
- [x] `scripts/check_agent_profiles.py`: `--ratchet` refuses committed-tree findings past the recorded baseline; `--update-baseline` re-records the tree-only sites
- [x] `tests/test_agent_profiles.py`: seven formerly host-fragile clean-tree tests isolate their live home
- [x] `tests/test_agent_profiles.py`: five new tests — scoped ⊆ global, clean-lane-greens-despite-drifted-sibling, unknown-profile exits 2, all-committed-lanes-pass-own-scope, ratchet-refuses-new-finding
- [x] `Makefile`: `check-agent-profiles-ratchet` target wired into the CI gate list
- [x] `tests/fixtures/agent-profiles-baseline.json`: tree-only finding baseline (currently `{}`)
- [x] `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` re-rendered with `make changes-index`
- [x] `make check-agent-profiles-ratchet`, `make lint`, `make check-docs`, `make check-wiring`, `make check-pr-hygiene`, `make openspec-tasks-check`, `make test-unit` and `make openspec-validate NAME=agent-profiles-lane-scope` green
