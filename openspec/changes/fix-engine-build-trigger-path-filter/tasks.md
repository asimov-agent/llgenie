# Tasks

- [ ] `scripts/engine_build_trigger.py` — drop the leading slash in BOTH run-list filters: `_existing_run_ids` (line 95) and `_push_group_holder` (line 180): `.path == ".github/workflows/engine-build.yml"`.
- [ ] `tests/test_engine_build_trigger.py` — set the mock's three run-list `.path` values to the real API shape `".github/workflows/engine-build.yml"` (lines 53/68/74), and add `test_the_mock_uses_the_real_api_path_shape` asserting the mock emits the no-leading-slash value so a regression cannot hide behind the wrong spelling.
- [ ] Prove the guard catches the bug: with the source filter still carrying the leading slash, the re-shaped mock must make discovery "new run not found" (a real dispatch under the bug → red); with the fix, the full `tests/test_engine_build_trigger.py` suite green (count the passing tests).
- [ ] Fast gates: `make lint`, `make openspec-validate NAME=fix-engine-build-trigger-path-filter` (exit 0), and the engine-build-trigger unit suite (via the repo's pytest venv) green.
- [ ] Docs trio: `docs/changes.d/2026-11-07-fix-engine-build-trigger-path-filter.md` (one table row) + `agent-wiki/2026-11-07-fix-engine-build-trigger-path-filter-*.md` (references #1982 and the fix) + regenerated `CHANGES.md`.
- [ ] PR body carries the six-section mapping (`Issue:`/`Fix:`/`Benefit:`/`Technical:` + `AGENTS:` + `closes #<issue>`), pushed to the fork, opened against upstream; never merge (#1088).
