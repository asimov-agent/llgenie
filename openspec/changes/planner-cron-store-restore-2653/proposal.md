# Proposal: planner-cron-store-restore-2653

## Why

Issue #2653: on 2026-11-11 the planner profile's cron store
`~/.hermes/profiles/llgenie-planner/cron/jobs.json` was overwritten with the
empty document `{"jobs": [], "updated_at": "2026-11-11T01:49:27.627279+00:00"}`
(69 bytes), silently removing all three scheduled jobs — the orchestrator tick
(`cc5d2bd4083a`, last fired 02:43:15) and the two sweepers
(`db0a3e1a3d7c`, `71c5192ebdba`). The planner stopped ticking for three days;
nothing re-armed the store. The sweepers were already restored by issue #2354
(PR #2654); the orchestrator tick job is still missing, so the tick drift gate
(`make check-tick-prompt`, #2159) reds with rc=2 (job not found) and the fleet
loses its 30-minute orchestrator heartbeat.

Root cause, established from receipts and logs (see agent-wiki entry): four
consecutive `hermes update --force` runs (01:47–01:57 CET, receipts
`update_20261111_004708…005642`, #1 failed) plus the same-night fleet align
config operations (`config-backups/strata-*-20261111`, snapshots 02:40–02:43)
drove a gateway drain/hard-interrupt restart loop (SIGTERM 02:48:24, 02:50,
02:53; "llgenie-planner still has live writers at shutdown; its admissions stay
for recovery", 02:49:14). 13 seconds later, at 02:49:27.627, the planner store
was saved as an empty `{"jobs": []}` in `cron.jobs.save_jobs()`'s exact
document shape, with the timestamp in UTC while every healthy gateway save
carries the +01:00 server-local offset — a helper/subscriber writing during
the torn-down window persisted a store it had read as empty. Hermes' own
"cron emptied out" restore net never fired (no restore line anywhere in
`update.log`), and Hermes' `load_jobs()` silently coerces a missing/invalid
`jobs` field to `[]`, so one such save is durable until someone re-creates the
jobs by hand.

## What Changes

- Restore the live orchestrator tick job `cc5d2bd4083a` in the planner profile
  store with its pinned id and the byte-identical versioned prompt
  `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`, mirroring the
  restored sweepers' conventions (30m interval, `deliver: local`, skills
  `llgenie-bot-orchestration`, terminal+skills toolsets).
- Prove the restored job dispatches: arm one live run and read its durable run
  id from `hermes cron runs cc5d2bd4083a`.
- Record the root-cause chain (evidence timestamps, mechanism, why the restore
  net didn't fire) in `agent-wiki/`.
- No gate code changes: the existing `make check-tick-prompt` and
  `make check-cron-drift` gates are the verification surface.

## Impact

- Affected specs: `planner-cron-store` (new capability)
- Affected code: none (host-side cron store state + docs/wiki/openspec only)
