# Tasks: pr-trigger-cell-detection

- [x] Add `repinned_cells(base, root)` to `scripts/check_engine_pins_published.py` (cell view of the tag-identity diff; missing-at-base counts as moved).
- [x] Derive `repinned_engine_ids` from `repinned_cells` + the params-FILE diff union (one code path, may-arm verdict unchanged).
- [x] Switch `scripts/engine_build_trigger.py` check/report/dry to per-cell dispatch with explicit `arch`; update docstrings.
- [x] Update `tests/test_engine_build_trigger.py` monkeypatch seam to `repinned_cells` and its assertions to the cell dispatch fields.
- [x] Add a GPU-cell-of-a-default-cpu-only-engine dispatch test and a synthetic-git-tree `repinned_cells` fixture test.
- [x] Update the trigger workflow header comment and the `docs/BOTS.md` dispatch-forms table; `make check-dispatch-forms` rc=0.
- [x] Add `docs/changes.d` fragment + `agent-wiki` entry naming issue #2590 and PR.
- [x] `make openspec-validate NAME=pr-trigger-cell-detection` rc=0 and `make lane-preflight` rc=0.
