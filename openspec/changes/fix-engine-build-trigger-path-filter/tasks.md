# Tasks

- [x] `scripts/engine_build_trigger.py` — drop the leading slash in BOTH run-list filters: `_existing_run_ids` (line 95) and `_push_group_holder` (line 191): `.path == ".github/workflows/engine-build.yml"`.
- [x] `tests/test_engine_build_trigger.py` — set the mock's three run-list `.path` values to the real API shape `".github/workflows/engine-build.yml"` (lines 57/78/84), and make `fake_gh_api` apply the `.path == "…"` literal it is handed so a regression reds the suite instead of hiding behind a shape lie.
- [x] Prove the guard catches the bug: with a leading-slash source filter the re-shaped mock returns ∅ ("new run not found" / empty `_existing_run_ids`), so a real dispatch under the bug ignores the produced run; with the fix the full `tests/test_engine_build_trigger.py` suite passes (13 tests), and a live `_existing_run_ids("asimov-agent/llgenie","gh")` returns non-empty and includes the freshly-dispatched producer `42399388147`.
- [x] Fast gates: `make check-docs` (rc 0), `make openspec-validate NAME=fix-engine-build-trigger-path-filter` (rc 0), and the engine-build-trigger unit suite green (13 passed via `~/llama-gguf-tools/.venv`).
- [x] Docs trio: `docs/changes.d/2026-11-07-fix-engine-build-trigger-path-filter.md` (one table row) + `agent-wiki/2026-11-07-fix-engine-build-trigger-path-filter.md` (references #2041 and the fix) — `make check-docs` green.
- [x] PR body carries the six-section mapping (`Issue:`/`Fix:`/`Benefit:`/`Technical:` + `AGENTS:` + `closes #2041`), pushed to the fork, opened against upstream; never merge (#1088).
