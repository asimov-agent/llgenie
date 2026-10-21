# Tasks

- [x] 1. `openspec/changes/hermes-smoke-fresh-store` — proposal + spec (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before any code
- [x] 2. `scripts/hermes_smoke.py` — no pre-run `state.db` refusal: snapshot the ids when the store is present, invoke Hermes, then fail loudly on no store / unreadable store / no new session, naming which
- [x] 3. `tests/test_hermes_smoke.py` — a fresh home with no store passes on a real session, a run that writes no store fails naming the path, an unreadable store still fails (replacing the test that pinned the pre-run refusal)
- [x] 4. `agent-wiki/2026-10-21-hermes-smoke-fresh-store.md` — the work record, referencing issue #471 and its PR
- [x] 5. Verified: `make test-unit` green with the changed cases, `make check-wiring`, `make check-docs`, `make lint`, `make openspec-validate NAME=hermes-smoke-fresh-store`, `make openspec-tasks-check` all exit 0 (`make test-unit`: 4966 passed, 6 deselected, 1015 s)
