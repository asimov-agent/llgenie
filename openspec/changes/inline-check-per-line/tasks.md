# Tasks

- [x] 1. `check_workflow_inline_scripts` scans per command (per line); the block-level exemption and the unused `GUARD_ALLOWED` constant are gone
- [x] 2. `registry-sync.yml` gets the gap markdown through the new `engine-skill-gap-md` make target (`.PHONY` + `##` help line + README line)
- [x] 3. Tests: a `gh` step hiding a script call is a finding, `make` on the same line clears it, and the check over the real tree finds nothing (`24 passed` in `tests/test_code_review.py`)
- [x] 4. Proven against the real thing: the pre-fix checker reports **0** findings for the pre-fix `registry-sync.yml`, the per-line checker reports **1** naming `python3 scripts/engine_skill_gap.py`
- [x] 5. README documents `engine-skill-gap-md`; `agent-wiki/2026-10-15-inline-check-per-line.md` records the work
- [x] 6. `make lint`, `make check-docs`, `make check-wiring`, `make check-dispatch-forms` and `make openspec-validate NAME=inline-check-per-line` exit 0
- [x] 7. The step's own test moves with it: `tests/test_engine_skill_gap.py::test_the_weekly_sync_regenerates_the_gap_and_spawns_a_tracking_issue` pins `make engine-skill-gap-md` (not `report --md`), so the sync workflow and the test that locks it cannot drift; `make test-unit` green
- [x] 8. #305 filed for `_steps()` yielding only a workflow's LAST `run:` block (measured `current=1` vs `real=20` for `ci.yml`), linked both ways and not folded into this change
