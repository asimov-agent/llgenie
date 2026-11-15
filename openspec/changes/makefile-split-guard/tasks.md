# Tasks — makefile-split-guard (issue #2674)

## 1. Committed budget source
- [x] 1.1 Create `tests/fixtures/makefile-line-budgets.json`: `mk_ceiling` 600 (measured max today 499), ratchet `Makefile` 977 with dated reason entry (measured `wc -l` on the landing tree).

## 2. Guard in scripts/check_wiring.py
- [x] 2.1 Declaration map: per-file declared target names over `Makefile` + `mk/*.mk` in include order (reuse `_makefile_list`), feeding `graph()`.
- [x] 2.2 Duplicate finding: name declared in >1 file → error naming the target and both files.
- [x] 2.3 Budget enforcement: load the committed budgets; over-ceiling file → error naming file + lines + ceiling; missing/malformed budget file → error.
- [x] 2.4 `report` prints the duplicate/budget line so `make check-wiring report` states the budget.

## 3. Tests in tests/test_wiring.py (controls in each direction)
- [x] 3.1 Planted duplicate across two includes → CLI rc=1 naming both files.
- [x] 3.2 Planted over-budget `mk/` file → rc=1 naming file + ceiling.
- [x] 3.3 Budget file removed → rc=1 (control: enforcement cannot be silently deleted).
- [x] 3.4 Real-tree tests: no duplicates; every `mk/*.mk` and the top `Makefile` fit ceilings DERIVED from the committed source (no baked numbers).
- [x] 3.5 Module suite `tests/test_wiring.py` green via `make test-unit`.

## 4. Docs + wiki
- [x] 4.1 `agent-wiki/2026-11-15-makefile-split-guard-2674.md` + `docs/changes.d/` fragment + `CHANGES.md` row; `make check-docs` green.

## 5. Verification
- [x] 5.1 `make openspec-validate NAME=makefile-split-guard` exits 0.
- [x] 5.2 `make check-wiring` and `make test-unit` green locally at the fix head; `make lane-preflight` OK.
