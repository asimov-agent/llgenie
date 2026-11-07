# 2026-11-07 — orchestrator-tick dispatch reads claim liveness from run status, not the marker TTL (issue #1959)

## What was wrong

`scripts/orchestrator_tick.py::measure()` decided "an `agent:implement` issue with no live claim"
through `bot_claims.occupied(comments, TICK, now)` WITHOUT `is_live`, so the automated dispatch gated a
bot claim on its marker TTL — exactly the half that disagreed with `bot_claims._decide`, which releases
a claim the moment the run that posted it concludes.

Measured at `origin/main@5045d5a1`: run-failure-reactor claimed `#1901` (run `42352164427`, ttl=240m,
"expires 11:39Z") and `#1926` (run `42353007098`, "expires 11:51Z"); both runs concluded with `failure`
seconds after posting. `bot_claims.occupied(..., is_live=run_is_live)` returned `None` for both —
already released — while the dispatch still reported them as "protected until ~11:39Z". rebase-bot run
`42354009408` correctly rebased both because the claims were dead, exposing the conflicting guidance.

## What changed

- `scripts/orchestrator_tick.py::measure()` passes `is_live` (wired to `bot_claims.run_is_live` — the
  ONE reader, issue #799) to `bot_claims.occupied`/`bot_claims.released`, matching every other reader.
  When a claim is released because its run concluded, the tick prints the measured release (the run id,
  e.g. "its run 42352164427 is no longer running") instead of a marker-TTL expiry sentence.
- The audit-dispatch source (`agents/llgenie-planner/skills/github-issue-triage/references/
  bot-claim-and-branch-sweep.md` and its SKILL.md pitfall) now states the run-liveness release comes
  first: a claim that names a `run=` is released the moment that run concludes, whatever the TTL says.
- Tests drive the measured #1901/#1926 case in BOTH the dispatch model (emits `IMPLEMENT-READY` for a
  dead-run claim, prints the run-id release) and the bot_claims reader (`occupied(..., is_live=...) is
  None`), plus the belt case that a live run still gates. OpenSpec change
  `orchestrator-tick-claim-liveness`.

## Verified

- `pytest tests/test_orchestrator_tick.py tests/test_bot_claims.py tests/test_claim_reader_guard.py`
  — all pass (88 in the rebound sweep too).
- `make openspec-validate NAME=orchestrator-tick-claim-liveness` exits 0; `lint`, `check-claim-reader`,
  `check-docs` green.

## Status

Issue #1959; PR from `agent/issue-1959-claim-liveness` against `asimov-agent/llgenie:main`. Never merge
(CI/auto-merge lands it).
