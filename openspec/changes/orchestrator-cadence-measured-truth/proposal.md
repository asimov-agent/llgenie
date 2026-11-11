# orchestrator-cadence-measured-truth

## Why

The planner's own documents asserted tick cadences that the live job does not deliver. The live
`llgenie-orchestrator-tick` has been configured `minutes: 30` since the owner directive 2026-11-08, yet
Hermes re-arms `next_run` from **completion** (`_advance_after_run()` → `finish + interval`), so the
delivered start-to-start cycle is interval + run duration. Measured at issue #2126 (34 fires from
executions.db): delivered start-to-start median **40.0 min** (min/max 37.0/43.0), median run duration
10.1 min. Documents quoting "45 minutes" (or quoting 30 as the cycle time) state a lying number, and a
planner that plans against a false cadence mis-times every dispatch (issue #2126).

## What Changes

Repatriate the measured truth into the planner's own text (all four locations found by the #2126 sweep):

- `agents/llgenie-planner/SOUL.md`: "fires every 45 minutes" → configured 30m with the measured
  delivered median 40.0 min and its cause.
- `orchestrator-tick-contract.md` Schedule + pitfalls lines: 30 = configured, 40.0 min = delivered,
  cause named (completion-based re-arm), pointer to #2340.
- `when-to-use-and-pass-shape.md`: "every 30–45 min" → configured `every 30m`, delivered median 40.0 min.

No interval change (owner directive: stays 30). Change notes per the change-note gate
(`agent-wiki/2026-11-09-orchestrator-cadence-measured-truth-2126.md` + `docs/changes.d` row).

## Impact

- Affected: `agents/llgenie-planner/SOUL.md`, `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/orchestrator-tick-contract.md`, `when-to-use-and-pass-shape.md`, change notes.
- Closes GitHub issue #2126 (PR #2447 carries the text this change records).
