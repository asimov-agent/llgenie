# The orchestrator tick's cadence statements tell the measured truth (issue #2126)

## What changed

Issue #2126 records the orchestrator tick's interval change (10m → 30m, owner directive 2026-11-08) and the
measurement that matters more than the config: the configured interval and the delivered interval diverge, and the
documents that stated the tick's cadence were lying about it. The planner-owned measurement (posted on #2126,
comment 6732036681, 34 fires from `$HOME/.hermes/profiles/llgenie-planner/cron/executions.db`, 30m era 2026-11-08
06:25 → 2026-11-09 04:42) found:

- **configured**: `every 30m`
- **delivered** (start-to-start, median): **40.0 min** (min/max 37.0/43.0, 0 of 33 gaps under 35 min)
- **median run duration**: **10.1 min**
- **root cause**: Hermes re-arms `next_run` from **completion** (`_advance_after_run()` → `finish + interval`),
  so delivered cycle = interval + run duration (30 + 10.1 ≈ 40.0). The same single cause explains the old 10m
  setting's 21.0 min median (10 + ~11 min run). Upstream scheduler fix tracked in #2340.

This vehicle repatriates that truth into the planner's own text so no document quotes a lying number again.

## Files changed (all inside `agents/llgenie-planner/`)

- `SOUL.md` — "fires every **45** minutes" → "fires every **30** minutes (measured start-to-start median 40.0 min,
  because Hermes re-arms next_run from completion: delivered cycle = interval + run duration — #2340)". This
  agent-instruction file's write is owner-consented for this fix (2026-11-09) and lands in this PR via the
  self-versioning git-commit vehicle.
- `skills/llgenie-bot-orchestration/references/orchestrator-tick-contract.md` —
  - the "**Schedule: `every 30m`**" line stays but now names 30 as the **configured** value and 40.0 min as the
    **delivered** median, so nobody quotes 30 as the cycle time,
  - the pitfalls bullet "`every 30m` has delivered gaps of 15–46 min" is replaced with the measured + root-caused
    form (34 fires, median 40.0 min, run duration median 10.1 min, one-line cause, pointing at #2340 and the
    executions.db query recorded on #2126).
- `skills/llgenie-bot-orchestration/references/when-to-use-and-pass-shape.md` — "(a cron job running this skill,
  every 30–45 min)" → configured `every 30m`, measured start-to-start median 40.0 min (see orchestrator-tick-contract.md).

The interval value itself is untouched (owner directive: stays 30). Change notes follow the #2272/#2136 convention
(this pair named their note `2026-11-08-orchestrator-tick-prompt-versioned-2136.md`).

## Verification

- Grep for cadence statements (`45 min|every 45|every 30|30–45|15–46|"six passes an hour"`) across
  `agents/llgenie-planner/`: **4 found, 4 fixed**, 0 contradicting statements remain.
- `git diff --stat` shows exactly the four changed text files.
- Gates run at the head: `make -s check-docs lint check-wiring check-pr-hygiene` (change-note gate + hygiene gate).
