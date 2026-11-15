# Tasks: makefile-tests-mk (issue #2677)

- [x] 1. Create worktree off latest `origin/main`; `make openspec-new NAME=makefile-tests-mk`
- [x] 2. Snapshot the base `make -qp` target inventory (pre-move) for the after-diff
- [x] 3. Extract the 18 blocks byte-identically into `mk/tests.mk` (incl. the
      `PY312`/`AGENTS_READ_*` definitions the stamp rule parses at load time)
- [x] 4. Remove the moved blocks from the top `Makefile`; append
      `include mk/tests.mk  # test-suite domain (issue #2677)` after `include mk/bots.mk`
- [x] 5. Prove the move: byte-identity of every moved block vs `HEAD:Makefile`;
      `make -qp` inventory identical; declared-target count 76 → 58 (−18);
      `make help` byte-identical
- [x] 6. `make check-wiring` green; `python3 scripts/unit_tests.py check` green
- [x] 7. `make test-unit` green locally (full hermetic suite)
- [x] 8. `docs/ARCHITECTURE.md` `mk/` row names `tests.mk` citing #2677;
      `docs/changes.d/` fragment + `make changes-index` row
- [x] 9. `agent-wiki/` entry naming issue #2677 and the PR
- [x] 10. `make openspec-validate NAME=makefile-tests-mk` passes; commit with the
      acceptance mirror, push, open the PR
