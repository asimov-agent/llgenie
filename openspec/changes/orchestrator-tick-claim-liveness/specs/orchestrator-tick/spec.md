# orchestrator-tick

## MODIFIED Requirements

### Requirement: the dispatch reads claim liveness from run status, not the marker TTL

The orchestrator tick's `measure()` MUST decide "an open `agent:implement` issue with no live claim"
through `bot_claims.occupied`/`bot_claims.released` with `is_live` wired to `bot_claims.run_is_live`
(the single run-liveness reader, issue #799). A claim whose run has CONCLUDED MUST release the subject
for dispatch immediately — regardless of the marker's TTL — because `bot_claims._decide` releases it
the same way; both the reader and the dispatch agree on the release point. A claim whose run is still
going (or whose run state cannot be verified) MUST keep the subject out of the dispatch. When a claim
is released because its run concluded, the tick MUST print the measured release (the run id), never a
marker-TTL expiry sentence.

WHEN `measure()` reads an issue whose newest claim names a run that has concluded
THEN the issue is dispatched as "no live claim" and the release is printed with the run id.

#### Scenario: a claim whose run died is released in the dispatch, same as in the reader (the #1901/#1926 case)
- **Given** an `agent:implement` issue whose newest claim is `bot-claim: fix-bot 2026-11-07T07:39:20Z
  fix ttl=240m run=42352164427` and the claim's run reports `status: completed`
- **When** `make orchestrator-tick` (or `measure()`) runs
- **Then** the issue is emitted as `IMPLEMENT-READY #1901 no live claim`, the release
  `42352164427 is no longer running` is printed on stderr, and `bot_claims.occupied(..., is_live=...)`
  returns `None` — both agree the claim is dead
- **Test:** `tests/test_orchestrator_tick.py::test_a_dead_run_s_claim_does_not_gate_the_dispatch`

#### Scenario: a claim whose run is still going keeps the subject out of the dispatch
- **Given** an `agent:implement` issue whose newest claim names a run that reports `status: in_progress`
- **When** `measure()` runs
- **Then** the issue is not emitted as `IMPLEMENT-READY` (the claim still holds)
- **Test:** `tests/test_orchestrator_tick.py::test_a_live_run_s_claim_still_gates_the_dispatch`
