# Tasks

- [x] `_dispatch_and_wait` treats a producer `conclusion` of `cancelled`/`skipped` as terminal — returns immediately with a named `cause` instead of polling until the deadline.
- [x] The wait loop's wall-clock bound fails with the producer run id and its last known status on expiry, never the bare `concluded <status>/<conclusion>` — the `stalled_behind` holder naming is preserved on the expiry line.
- [x] Regression tests drive the wait loop with a cancelled producer and a skipped producer (both terminate with the named cause) and an in_progress producer past the bound (expiry names run 77 + last status).
- [x] Existing `tests/test_engine_build_trigger.py` battery stays green (12 passed: 9 prior + 3 new); the two #1860 stall tests updated to the new expiry message shape.
- [x] Docs per convention: this openspec change dir accompanies the code; `docs/changes.d/2026-11-07-engine-build-trigger-cancelled.md` + `agent-wiki/` note + `CHANGES.md` row in the PR.
- [x] PR carries `closes #1931`; `make lane-preflight` green and `make openspec-validate NAME=engine-build-trigger-cancelled` passes.
