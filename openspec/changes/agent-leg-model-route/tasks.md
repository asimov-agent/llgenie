# Tasks: agent-leg-model-route

- [x] Create this OpenSpec change (proposal + spec delta + tasks) before any code
- [x] Add `scripts/hermes_model_route.py`: profile-home-first store read, window-filtered newest
      session, one `model-route: <model-id>` line, loud non-zero exits (missing store / no
      session in window / no model value), stdlib-only, no secrets
- [x] Print the same `model-route: <model-id>` line in `scripts/hermes_smoke.py` for the session
      it creates (after its verdict, verdict semantics unchanged)
- [x] Wire the report into the nine Hermes leg recipes (mk/bots.mk, mk/agents.mk, mk/engines.mk):
      start-epoch capture, `hermes` first, report second, `exit` with Hermes' status
- [x] Add `tests/test_hermes_model_route.py` (fixture sqlite stores: profile-first resolution,
      global fallback, window filter, all three loud failures, line shape)
- [x] Register the script in `scripts/package-layers.json`; document the report in `docs/BOTS.md`;
      agent-wiki entry + `docs/changes.d/` fragment + `make changes-index`
- [ ] Gates green at the final head: targeted pytest battery, `make check-secret-output`,
      `make check-wiring`, `make check-docs`, `make openspec-validate NAME=agent-leg-model-route`,
      live proof `make hermes-smoke` prints a `model-route: ` line
- [ ] Final alignment: issue #2931 body, PR body, and commit text carry the same ticked AC items
      with replayable proven clauses at the final head
