# Tasks — hermes-smoke-envelope-kind (issue #2269)

- [x] 1. OpenSpec change: `proposal.md`, `specs/hermes-smoke-envelope-kind/spec.md`, this checklist
- [x] 2. `scripts/hermes_smoke.py`: `envelope_kind(body)` classifies a tool-result body into `lost` / `truncated` / `empty` / `ok`, and `evaluate` names a lost or truncated terminal envelope on the channel instead of the single generic message; a well-formed envelope with genuinely empty output still reads as an empty command (negative control)
- [x] 3. `tests/test_hermes_smoke.py`: a lost envelope is named not an empty success; a truncated envelope is named; a genuinely empty result is the negative control; real output replayed as empty success is detected; existing cases unchanged
- [x] 4. `agent-wiki/2026-11-08-hermes-smoke-envelope-kind.md` note + `docs/changes.d/2026-11-08-hermes-smoke-envelope-kind.md` fragment + rendered `CHANGES.md` row
- [x] 5. Verified: the 4 new tests red on the pre-fix code and pass after (hermetic unit run), and `make openspec-validate NAME=hermes-smoke-envelope-kind` green
