# planner cron store restore — orchestrator tick re-armed after the 2026-11-11 wipe

Implements issue **#2653** (closes #2653; origin lane PR #2654 for issue #2354).
OpenSpec change: `planner-cron-store-restore-2653`.

## What was verified (root cause, measured on the host)

- The wipe: `$HOME/.hermes/profiles/llgenie-planner/cron/jobs.json` read
  `{"jobs": [], "updated_at": "2026-11-11T01:49:27.627279+00:00"}` (69 b). The last
  healthy backup `jobs.json.bak-pre2141-1794197300` (20,569 b, 2026-11-09) still held
  all three jobs; the orchestrator tick `cc5d2bd4083a` had 180 completed runs there.
- The window: four `hermes update --force` runs 01:47–01:57 CET (receipts
  `update_20261111_004708` … `update_20261111_005642`, the first one failed) plus the
  same-night fleet `strata-align` config operations (`config-backups/strata-*-20261111`)
  drove a gateway drain/hard-interrupt restart loop — SIGTERM at 02:48:24, 02:50, 02:53;
  02:49:14: "llgenie-planner still has live writers at shutdown; its admissions stay for
  recovery". 13 s later, at **02:49:27.627 UTC**, the store was saved as the empty
  document in `cron.jobs.save_jobs()`'s exact shape — while every healthy gateway save
  carries the +01:00 server-local offset, proving a helper/subscriber persisted a store
  it had read as empty during the torn-down window.
- Why nothing healed it: Hermes' "cron emptied out" restore net never fired (no restore
  line in `update.log`), and `load_jobs()` silently coerces a missing/invalid `jobs`
  field to `[]` — one such save is durable until the jobs are re-created by hand.

## What was done

- Restored the live orchestrator tick job `cc5d2bd4083a` (pinned id) with the
  byte-identical committed prompt `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`,
  30 m interval, `deliver: local`, skill `llgenie-bot-orchestration`, toolsets
  terminal+skills, `catch_up: true` — mirroring the sweepers #2354 restored.
- Proved dispatch: durable rows in `hermes -p llgenie-planner cron runs cc5d2bd4083a` —
  `294652caab21401bbfadd8909fe5faae` **completed** (source=direct, 2026-11-14T02:39:54+01:00)
  and the schedule resumed (`Last run 03:34 ok`, `Dispatch: on time`; the 03:10 builtin
  attempt shows `Fire claim ownership lost` — the armed direct run overlapping the tick,
  self-healed on the next tick).

## Gate replay

- `make check-tick-prompt` → **rc=0** ("live prompt == versioned") — was rc=2 (job not found).
- `make check-cron-drift` → rc=1 **while PR #2654 is unlanded**: the live sweeper prompts
  carry the #2354 lane's record-step text and the gate's own message calls this exact state
  "review not landed". Replay rc=0 after #2654 lands on main (issue AC4 is ticked then).

## Decisions

- No gate code changes in this lane (host restore + records only). A durable guard —
  fail LOUD when a profile store's expected job ids vanish (the wipe would otherwise
  again stay invisible to every repo-side gate) — is filed as its own follow-up issue.
- `make sync-agent-profile PROFILE=llgenie-planner` re-synced 965 files at the #2354 lane
  head (2 prompts updated), keeping tree and live profile in step.
