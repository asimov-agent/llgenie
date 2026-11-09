# A drift gate for the two new planner crons (issue #2359)

## Why

The planner runs three recurring crons; only the orchestrator-tick was versioned. The two new ones
(auto-approve-merge, auto-rebase-resolve) lived only in the live jobs.json, so they evaporated on the
next sync and every planner re-create. A recurring rule must be readable and diffable in the tree so
a regression is caught by a gate, not re-discovered when a cron silently stops.

## What changes

`scripts/check_cron_drift.py` + `make check-cron-drift` compare each committed prompt under
`agents/llgenie-planner/prompts/` against the live job's `prompt`, host-only like `check-tick-prompt`.

## Impact

A host lane can verify the tree and the live scheduler agree; CI stays hermetic (no live jobs.json on
a runner). No gate weakened; the new gate is opt-in host verification.
