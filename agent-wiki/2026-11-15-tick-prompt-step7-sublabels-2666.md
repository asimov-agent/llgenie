# Tick prompt STEP 7 sub-labels renumbered 6a/6b/6d -> 7a/7b/7c (#2666)

Issue: #2666. PR: #2690. OpenSpec change: tick-prompt-step7-sublabels.

## What was verified
- `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`: STEP 7's sub-items now read `7a`/`7b`/`7c` (consecutive; skipped `6c` retired), STEP 6 keeps `6a`-`6d` unchanged, and the report template cites `(step 7b)` beside the duplicate-collapse rule (`grep -c '(step 6b)'` -> 0 at head).
- Fold precondition (#791 truncation trap) measured at this head: the two planner prompts flagged `live-edited-not-tree` at `fc39b4180` (`llgenie-auto-approve-merge.md` 1749 b, `llgenie-auto-rebase-resolve.md` 2330 b) are tree==live on `origin/main` already (folded by the #2653 restore + #2679 reconcile, PRs #2669/#2687); `cmp` identical at head. The tick prompt's 4 live-only lines from 2026-11-14T04:34:39Z were likewise already merged into main; the only tree->live delta after this change is the deliberate renumbering, synced with `FORCE=1` (the sync guard's refusal text matched that exact intent).
- `make sync-agent-profile PROFILE=llgenie-planner` then `CHECK=1`: 965 files byte-identical tree<->live.
- Gates: `make -s check-docs` rc 0; `make openspec-validate NAME=tick-prompt-step7-sublabels` passes; lint/wiring/workflows/agents gates via `make lane-preflight` OK.

## Current status
Done on branch agent/issue-2666-tick-prompt-sublabels; text-only prompt change + note pair; no gate code touched.
