# Versioning the tick prompt's LOAD-20-TO-TRIAGE step 6d (issue #2136, #2328)

## What changed

The live orchestrator tick prompt (`~/.hermes/profiles/llgenie-planner/cron/jobs.json`, job `cc5d2bd4083a`)
grew **STEP 7 substep 6d** — the owner mandate (2026-11-09): *"LOAD 20 NEW UN-PR'D `agent:implement`
ISSUES INTO THE KANBAN TRIAGE LIST EVERY PASS"* — carding each candidate to its OWNING lane per the
#2073/#2270 ownership map, and carding every open PR's closing issue as a read-only mirror. It also
acquired the `/tmp` collector pass specifics (#2141/#794/#2262), the lane-contract skill-materialisation
wording (#2260), and the `$REPO/scripts` prompt-refresh seams.

The committed copy `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md` (16,569 b) lagged the
live prompt (18,653 b) and did **not** carry 6d — so the #2136 byte-identical drift contract was broken
and the `check-tick-prompt` gate would red. This PR re-snapshots the versioned prompt **verbatim** from
the live jobs.json (18,653 b, `6d. LOAD 20 NEW UN-PR'D …` present ×1), restoring tree==live fidelity so
a fresh worktree and the drift gate both match what the running job actually does.

## Verification (at the new head)

- `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md` = 18,653 b, byte-identical to live
  (`check_tick_prompt.py --live jobs.json` → "OK live prompt == versioned (18653 b)").
- `grep -c "LOAD 20 NEW UN-PR"` committed file → 1 (was 0).
- `make check-docs` rc=0 (census `7b8bc3e8` valid), `make lint`, `make check-wiring` green.
- 0 hardcoded `/home/<user>` additions.

## Decisions / scope

- This is the **#2136 drift-refresh** for the 6d step: it makes the versioned prompt byte-identical to
  the running job again (the #2136 AC). It supersedes the stale committed copy and covers the LOAD-20
  acceptance item that #2328 inherited from the owner mandate and routed here.
- Not a SOUL change, not a script change. The live jobs.json is set at the running job; `check-tick-prompt`
  remains the drift gate.

## Issue / PR

Implements/refreshes #2136 (and the #2328-routed 6d tick-prompt AC). No merge/arm (#1088).
