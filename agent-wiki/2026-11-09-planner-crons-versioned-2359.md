# Versioning the two new planner crons (issue #2359)

## What changed

The LLGenie planner runs THREE recurring crons, but only the orchestrator-tick was versioned/tracked
(#2136). The two added this session existed only in the live cron store:

1. **`db0a3e1a3d7c` — llgenie-auto-approve-merge (30m)** — now committed at
   `agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md`. Runs `make auto-merge-recheck REPO=asimov-agent/llgenie
   MAX=50`, approves bot-authored green PRs, defers owner-authored (the #1088 identity constraint),
   records on #2101 / the tick.
2. **`71c5192ebdba` — llgenie-auto-rebase-resolve (30m)** — now committed at
   `agents/llgenie-planner/prompts/llgenie-auto-rebase-resolve.md`. Fetches origin/main, measures DIRTY/CONFLICTING +
   BEHIND PRs, dispatches each to `llgenie-pr-merge-conflict`, excludes engine-chore.

Both files are **byte-identical to the live prompt** at the snapshot sha (auto-approve-merge 1658 b,
auto-rebase-resolve 2194 b). The change-note trio records them; `check-cron-drift` (a gate parallel to
`check-tick-prompt`, landing under `scripts/`+`Makefile` in the ci-pipelines-maintainer lane's vehicle)
reads both committed prompts against the live jobs.

## Verification (at the head)

- `agents/llgenie-planner/prompts/llgenie-auto-approve-merge.md` == live `db0a3e1a3d7c` prompt (1658 b, byte-match true).
- `agents/llgenie-planner/prompts/llgenie-auto-rebase-resolve.md` == live `71c5192ebdba` prompt (2194 b, byte-match true).
- `make check-docs`/`lint`/`check-wiring` green; change-note trio present.
- 0 hardcoded `/home/<user>` additions.

## Decisions / scope

- **No duplicate cron for LOAD-20-to-kanban**: the orchestrator-tick's STEP 7 substep 6d already IS the
  "import 20-30 new un-PR'd issues + triage" mechanism (#2359 AC4). This PR does not add a second cron,
  and documents that 6d as the single kanban-load path.
- The drift gate is a `scripts/` + `Makefile` change (the #791-pipeline lane's boundary). This PR is the
  docs/`agents/` half: it commits the two prompts. The gate lands in the ci-pipelines-maintainer lane's
  vehicle referencing these files; both prompts are committed now so tree==live for them.

## Issue / PR

Implements #2359 (docs half: prompts + trio). Never merged by hand, never armed (#1088).
