# 2026-11-14 — Sweeper record target repointed to a never-closing tracker (#2354)

Implements issue #2354 (OpenSpec change `auto-merge-sweep-record-target-2354`). PR: see #2354.

## What was verified

- **Dead record target measured**: `agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md`
  step 5 recorded "on the tick card (id cc5d2bd4083a) or on issue #2101"; `hermes kanban show
  cc5d2bd4083a` → no such task; `gh issue view 2101 --json state` → CLOSED. The sibling
  `llgenie-auto-rebase-resolve.md` step 6 carried the same fallback ("the tick card or
  #2101/#2158").
- **New durable target**: issue **#2652** "sweepers: rolling record tracker (auto-merge +
  auto-rebase, never closes)" — OPEN (verified `gh issue view 2652`), with the two fixed first
  lines (`[sweep …]`, `[rebase-sweep …]`) written into its body; implementation PRs must never
  `closes` it.
- **Both record steps rewritten** to name only #2652, once per run, fixed greppable first line,
  per-PR reasons.
- **Live jobs restored**: the planner `cron/jobs.json` had been emptied on 2026-11-11
  (`jobs: []`, updated_at 2026-11-11T01:49:27Z). Jobs `db0a3e1a3d7c` (auto-merge, new prompt) and
  `71c5192ebdba` (auto-rebase-resolve, new prompt) were restored with pinned ids, 30m cadence,
  prompts byte-identical to the committed copies; `make check-cron-drift` → `OK db0a3e1a3d7c … OK
  71c5192ebdba … 2 job(s) checked`, rc=0. Backup kept at `jobs.json.bak-pre2354-<ts>`.
- **AC3 real sweep**: `make auto-merge-recheck REPO=asimov-agent/llgenie MAX=50` rc=0 evaluated 1
  open PR (#2651, deferred: mid-flight run at f560afa4, #1551 rule) and recorded on #2652 as
  comment `6868792116` with the fixed first line + deferral reason.
- **AC2 grep replay** at the lane head: `git grep -n 'cc5d2bd4083a' -- agents/ scripts/ .github/
  docs/` — remaining hits are the *cron-job* id of the orchestrator tick inside the gates/contracts
  that drive it (`check_tick_prompt.py` `LIVE_JOB_ID`, `check_cron_drift.py` docstring,
  `llgenie-bot-orchestration` tick-contract references) and dated changes.d records; no record step
  names the dead card anymore (`git grep -n 'Record on the tick card' -- agents/` rc=1).
- **AC1 replay**: `gh issue view 2652 --repo asimov-agent/llgenie --json state` → `OPEN`.

## Decisions

- One tracker for both sweepers (title generalized) instead of two durable surfaces.
- The emptied planner cron store itself (orchestrator-tick job `cc5d2bd4083a` gone, 180 completed
  runs in the last backup) is out of #2354's scope and filed as its own issue **#2653**; this lane
  only restores the two jobs its drift gate needs.

## Current status

Implemented; gates replayed at the lane head. Fleet outage (#2653) remains open for the tick-job
restore + root-cause of the 2026-11-11 wipe.
