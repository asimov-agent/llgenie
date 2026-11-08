## 1. Capture the evidence

- [x] Add `_dump_serve_log()` — the in-container serve-log tail plus the `docker logs --tail 60` tail
- [x] Call it on the readiness-timeout path, before the caller's `finally` removes the container
- [x] Call it on the early-exit path (replacing the bare `docker logs` call)
- [x] Name an engine that produced no output as `EMPTY/absent (no engine output captured)`

## 2. Nothing weakened

- [x] The readiness bound, the assertion and the exit codes are unchanged
- [x] No image tag input is touched, so no engine is re-tagged or re-published
- [x] The dump is best-effort and only runs after a failure that already returned 1

## 3. Proof

- [x] `tests/test_engine_image_serve_log.py` reds on the parent (fix stashed) and greens with it
- [x] Docs trio (#1123): this openspec change + `agent-wiki/` note + `docs/changes.d/` row
