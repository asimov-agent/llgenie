# Proposal: auto-merge-sweep-record-target-2354

## Why

Issue #2354: the 30m auto-merge sweeper's record step (step 5 of its procedure) names a kanban
tick card (`cc5d2bd4083a`) that resolves to "no such task" and closed issue #2101 as fallback, so
the sweep's per-run counts + per-PR deferral reasons land on a closed thread no lane reads. Measured
this pass (main@673b7fd8): sweep ran `make auto-merge-recheck REPO=asimov-agent/llgenie MAX=50`,
26 PRs evaluated, 2 approvals, and the record comment landed on CLOSED #2101 (comment
6733473325). The sweep cadence is proven live (#2136) but its record output has no live durable
target.

## What Changes

- The sweeper's record step names EXACTLY ONE target: the rolling record tracker issue **#2652**
  ("sweepers: rolling record tracker (auto-merge + auto-rebase, never closes)"), recorded once per
  run with a fixed greppable first line `[sweep <UTC-stamp>] merged=<n> approved=<n> deferred=<n>`
  plus one line per deferred PR with its reason. The sibling `llgenie-auto-rebase-resolve.md` step 6
  (same dead-card fallback: "the tick card or #2101/#2158") is rewritten the same way with its
  `[rebase-sweep <UTC-stamp>]` first line.
- The versioned procedure copy `agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md` step 5
  is rewritten to name only #2652 (no tick-card id, no closed-#2101 fallback).
- The live planner cron job `db0a3e1a3d7c` (llgenie-auto-approve-merge) is restored/repointed with
  the corrected prompt byte-identical to the committed copy (the host-side half of the issue,
  tracked via #2136); `make check-cron-drift` proves the byte-sync. The sibling job
  `71c5192ebdba` (llgenie-auto-rebase-resolve) is restored byte-identical to its committed copy as
  part of restoring the emptied planner jobs.json this lane must touch anyway.
- One real sweep run records on #2652 in the fixed format (AC3 evidence).
- Historical record lines (CHANGES.md, agent-wiki notes) that name `cc5d2bd4083a` are kept as dated
  records: there the id is the *cron job* id of the orchestrator tick, which exists — the dead card
  was the kanban lookup the sweeper procedure wrongly used. The live procedure dirs
  (`agents/`, `scripts/`, `.github/`, `docs/`) must carry no reference to it.

## Out of scope (separate linked issues)

- Why the planner `cron/jobs.json` was emptied 2026-11-11 (`jobs: []`) and the loss of the
  orchestrator-tick job (`cc5d2bd4083a`) + kanban fleet state: filed as its own issue (#2653),
  linked from this lane's PR `Not covered`.
