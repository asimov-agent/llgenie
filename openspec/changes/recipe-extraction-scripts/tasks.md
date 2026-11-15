# Tasks: recipe-extraction-scripts (issue #2675)

- [x] 1. Create worktree off latest `origin/main`; `make openspec-new NAME=recipe-extraction-scripts`
- [x] 2. Capture bases at `dcfb96b7df`: `make help` (59 lines, sha256), the 51-entry
      `ci-unit` invocation list, the five recipe line counts (60/51/15/15/12)
- [x] 3. `scripts/make_help.py` + commit the base capture as `tests/fixtures/make-help-base.txt`;
      `help` recipe -> 1 wrapper line; `cmp` proves byte-identity
- [x] 4. `scripts/ci_unit.py` (`MAKE_SEQUENCE`, `sequence_targets()`, `--dry-run`, fail-fast);
      `ci-unit` recipe -> wrapper; record base vs head invocation lists byte-equal
- [x] 5. Extend `scripts/check_wiring.py` + `scripts/issue_bot_gates.py` with the
      entry-point sequence seam; keep #475 classification and CI closure green; update their
      fixture tests
- [x] 6. `scripts/test_clean.py` (runtime-agnostic orphan prune) + thin `test-clean` recipe
- [x] 7. `scripts/build_server.py` (detect -> build with tee -> stamp) + thin `build-server` recipe
- [x] 8. `scripts/published_engine.py` (usage guard, pull-published, `test-engine-image`
      delegation, `PE_TEST` seam, CI_HOME pair) + thin `test-published-engine` recipe
- [x] 9. Hermetic tests: `tests/test_ci_unit_stage.py`, `tests/test_make_help_stage.py`,
      `tests/test_test_clean_stage.py`, `tests/test_build_server_stage.py`,
      `tests/test_published_engine_stage.py` (stubbed subprocess seam, no network marker)
- [x] 10. `make check-wiring`, `make check-workflows`, `make check-docs`,
      `make issue-bot-gates`, `make issue-bot-gates-check` green; `make -qp` inventory identical
- [x] 11. `make test-unit` green locally (full hermetic suite)
- [x] 12. `docs/ARCHITECTURE.md` + `docs/changes.d/` fragment + `agent-wiki/` entry naming
      issue #2675 and the PR
- [x] 13. `make openspec-validate NAME=recipe-extraction-scripts` passes; commit with the
      acceptance mirror, push, open the PR (closes #2675)
