# Tasks

- [x] `_dispatch_and_wait` treats a producer `conclusion` of `success` as **terminal** — returns immediately with `conclusion: "success"` instead of polling until the deadline; the awaited run's `status`/`completed_at` field is ignored for the terminal decision, exactly as #1936 did for `cancelled`/`skipped`.
- [x] `check()`'s existing `conclusion == "success"` branch reports `[will] OK engine=<e>: producer run <id> success` and returns 0 for a success producer whose status snapshot is in_progress.
- [x] Regression test `test_success_producer_terminates_even_with_status_not_completed` drives the wait loop with `{status: in_progress, conclusion: success}` and `--wait-min 0`, and asserts the success verdict (rc 0) — proven to FAIL FAST (deadline expiry) against the pre-fix code.
- [x] Existing `tests/test_engine_build_trigger.py` battery stays green (13 passed: 12 prior + 1 new).
- [x] Docs per convention: this openspec change dir accompanies the code; `docs/changes.d/2026-11-07-engine-build-trigger-success-conclude.md` + `agent-wiki/` note + `CHANGES.md` row in the PR.
- [x] PR carries `closes #1994`; `make lane-preflight` green and `make openspec-validate NAME=engine-build-trigger-success-conclude` passes.
