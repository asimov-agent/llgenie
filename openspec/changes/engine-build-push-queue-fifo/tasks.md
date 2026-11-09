# engine-build-push-queue-fifo — tasks

- [x] 1. `openspec/changes/engine-build-push-queue-fifo` — proposal + spec (G/W/T, a `- **Test:**` line) + this checklist, written before the code
- [x] 2. `.github/workflows/engine-build.yml` — add `queue: max` beside `cancel-in-progress: false` in the shared push `concurrency:` group, with the #2294 rationale comment
- [x] 3. `tests/test_ci_concurrency.py` — `test_engine_build_pending_push_queue_runs_fifo` parses `concurrency.queue == "max"`
- [x] 4. Negative control measured locally: reverting the `queue:` key reds the new test; restored it is green
- [x] 5. `make check-workflows` + `make check-wiring` green; change-note trio (agent-wiki + docs/changes.d + CHANGES.md)
