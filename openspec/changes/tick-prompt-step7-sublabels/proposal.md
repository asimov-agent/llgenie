## Why

Issue #2666: the planner tick prompt `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md` numbers STEP 7's sub-items `6a / 6b / 6d` — leftovers from before the #2159 step renumbering, with `6c` skipped — so one label names two different rules (STEP 6's `--message` rule vs STEP 7's duplicate-collapse rule) and tick-report citations like `(step 6b)` are ambiguous.

## What Changes

- Renumber STEP 7's sub-items in the tree prompt: `6a`→`7a`, `6b`→`7b`, `6d`→`7c` (consecutive; STEP 6 keeps `6a`–`6d`).
- Update the report-template cross-reference from `(step 6b)` to `(step 7b)` (the duplicate-collapse rule it means).
- Prove the two planner prompts formerly flagged `live-edited-not-tree` (measured at `fc39b4180`) are tree==live at this head (the #2679 sync landed them identical), so `make sync-agent-profile` can never truncate live planner edits (the #791 trap).
- Carry the change-note trio (agent-wiki + docs/changes.d + changes-index) although the #1123 gate is silent on `agents/*/prompts/**` (lane discipline per #1725).

## Impact

- Affected spec: `orchestrator-tick-procedure` (new capability delta: sub-item labels resolve to one rule).
- Affected code: `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md` (text-only).
- No gate code changes. Closes #2666.
