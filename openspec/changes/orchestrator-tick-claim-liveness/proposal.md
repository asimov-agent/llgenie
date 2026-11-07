# orchestrator-tick-claim-liveness

## Why

The planner's dispatch producer and `scripts/bot_claims.py` disagreed about when a bot claim stops
protecting a subject. `bot_claims._decide` releases a claim the moment the run that posted it
concludes (`is_live=run_is_live` — the one reader, issue #799), but the orchestrator tick's
`measure()` called `bot_claims.occupied(comments, TICK, now)` WITHOUT `is_live`, so the automated
dispatch gated on the claim's MARKER TTL instead — a claim whose run died seconds after posting still
looked "protected until ~11:39Z".

Measured at `origin/main@5045d5a1` (2026-11-07 09:31Z): the run-failure-reactor claimed `#1901` (run
`42352164427`, ttl=240m, "expires 11:39Z") and `#1926` (run `42353007098`, "expires 11:51Z"); both runs
concluded with `failure` seconds after posting (`42352164427` ended 07:39:25Z, `42353007098` ended
07:51:48Z). `bot_claims.occupied(..., is_live=run_is_live)` returned `None` for both — already
released — while the dispatch said they were still held. rebase-bot run `42354009408` correctly picked
both because the claims were dead, exposing the conflicting guidance.

## What Changes

- `scripts/orchestrator_tick.py::measure()` passes `is_live` to `bot_claims.occupied` (and
  `bot_claims.released`) so the dispatch reads claim liveness from run status the same way every other
  reader does — the ONE reader behind `bot_claims.run_is_live`, never a re-opened probe (issue #799).
  When a claim is released because its run concluded, the tick prints the release (the run id, e.g.
  "its run 42352164427 is no longer running") instead of the marker TTL.
- "The audit dispatch (or its source)" — the planner's skill reference
  `agents/llgenie-planner/skills/github-issue-triage/references/bot-claim-and-branch-sweep.md` and the
  SKILL.md pitfall now say the run-liveness release comes first: a claim names a `run=`, that run's
  conclusion releases the subject NOW regardless of the TTL, and the reader says which one it used.

## How It Fixes the Cause

One definition of "when does this claim stop holding" is now used by the bot_claims reader AND the
dispatch producer: a claim holds while its run is live OR until its TTL — the run decides first, so a
dead run's claim releases a subject immediately, and a "do not touch until ~11:39Z" is only issued for
work the protocol actually still holds. The test drives the measured #1901/#1926 case in both places.

Issue: [#1959](https://github.com/asimov-agent/llgenie/issues/1959).

## Out of Scope

- The standing-rule prose in `agents/*/SOUL.md` — that half is issue #1960 (documentation lane).
