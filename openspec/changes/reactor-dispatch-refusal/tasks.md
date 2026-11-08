# Reactor dispatch refusal — tasks

- [x] `DispatchRefused`, `missing_scope`, `parse_dispatch_refusal`, `report_repair_unavailable` in `scripts/run_failure_reactor.py`
- [x] route A catches the refusal: PR comment + `bot-done` claim release + `::warning::` + exit 0
- [x] workflow `DISPATCH_TOKEN` comment names the required scope and the refusal path
- [x] `docs/BOTS.md` reactor section documents the refusal route
- [x] change-note trio (agent-wiki + docs/changes.d + CHANGES.md) keyed to #2086
- [x] tests: 3 new cases (403 posted + non-blocking, unparseable surfaced, status→scope table)
- [x] guard-prove: the 3 new cases red against the old script (`assert 1 == 0`, `AttributeError`), green after — `26 passed`
- [x] `make lane-preflight` → `preflight: OK (6 gate(s))`
- [x] `make openspec-validate NAME=reactor-dispatch-refusal` green
