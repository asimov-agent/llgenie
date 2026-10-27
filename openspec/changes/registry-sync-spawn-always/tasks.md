# Tasks — registry-sync-spawn-always (issue #758)

- [x] 1. OpenSpec change: `proposal.md`, `specs/registry-sync-spawn/spec.md`, this checklist
- [x] 2. `.github/workflows/registry-sync.yml`: the spawn step carries `always() && steps.diff.outputs.changed`, and its recipe re-checks the watched store diff (`git diff --quiet` → `exit 0`) before `make spawn-engine-skill-issues`
- [x] 3. The PR step keeps `if: steps.diff.outputs.changed` alone (no `always()`)
- [x] 4. Contract test `tests/test_engine_skill_gap.py::test_the_spawn_step_runs_even_when_a_gate_above_is_red`
- [x] 5. Contract test `tests/test_engine_skill_gap.py::test_the_spawn_recipe_files_nothing_without_a_diff` (the recipe executed in a real git checkout)
- [x] 6. `docs/BOTS.md` records the always() on the spawn step; `agent-wiki/2026-10-27-registry-sync-spawn-always.md` + the `CHANGES.md` row record the change
- [x] 7. Verified: `make check-workflows`, `make check-dispatch-forms`, `make check-docs`, `make check-wiring` and `scripts/lint_linefeeds.py` green; the full unit suite run on the host (14528 passed, one pre-existing `MAKELEVEL`-only failure in `tests/test_repo_slug.py`)
