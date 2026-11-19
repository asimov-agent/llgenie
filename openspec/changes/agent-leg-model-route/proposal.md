# Proposal: agent-leg-model-route

## Why

Issue #2931. Since the model chain from #2929 landed, nothing reports WHICH chain member
actually served a bot leg. Transcripts are scrubbed and Hermes logs nothing to stdout about the
provider, so a leg silently served by the paid last-resort model looks identical to a healthy
leg served by the free primary. The owner cannot see the chain policy working or failing, and
fallback usage is not measurable.

## What Changes

- Add `scripts/hermes_model_route.py`: after a leg finishes, read the lane's Hermes session store
  (the profile home's `state.db` first — Hermes `-p <lane>` runs land their session in
  `$HERMES_HOME/profiles/<lane>/state.db`, global store as fallback) and print exactly one
  `model-route: <model-id>` line naming `sessions.model` for the newest session started inside
  the leg's window. A missing store, no session in the window, or a session without a recorded
  model exits non-zero with a named failure — never a fabricated line.
- Wire the report into all nine Hermes bot-leg invocations (mk/bots.mk, mk/agents.mk,
  mk/engines.mk): run the report after `hermes` finishes and exit with `hermes`' own status, so
  the leg keeps its current pass/fail semantics and the line lands inside the scrubbed log tail.
- `make hermes-smoke` prints the same `model-route: <model-id>` line for the session it created,
  so the existing smoke gate itself produces the acceptance evidence.
- Add `tests/test_hermes_model_route.py` proving the read, the window filter, the loud failures,
  and that the line carries ONLY the model id (the secret gate `make check-secret-output` stays
  green).
- Register the script in `scripts/package-layers.json` (Bots and automation) and document the
  report in `docs/BOTS.md`.

## Out of scope (separate issues, already filed)

- Catalog staleness monitoring of the five `:free` chain members — #2930.
- Aggregate dashboards over many legs — the issue defers "aggregate later if wanted".
