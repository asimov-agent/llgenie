# Proposal: scripted CI monitor triage (issue #3019)

## Why

`make ci-monitor` (issue #3013) prints `MAIN-RED` / `PR-CHECKS` incidents, but nothing converts an
incident line into a tracked work item: filing is left to the discretion of whichever agent the
monitor wakes, and the run-failure reactor (`make run-failure-reactor`, issue #286) is never fed by
the monitor. A red main pipeline or a failed PR pipeline therefore sits untracked between ticks —
the exact failure the 2026-11-14 watchdog removal exposed. The sanctioned monitor cron also lives on
`llgenie-ci-pipelines-maintainer`, away from the planner that drives the board, and nothing in the
contract says a lane owner must fix its own failed PR pipeline while its CI verdict is pending.

## What Changes

1. `scripts/ci_monitor.py` gains `--triage`: after printing the byte-stable snapshot, each
   `MAIN-RED` incident and each `PR-CHECKS` incident resolves the completed failed run id(s) on the
   incident's head (`gh run list -c <sha>`, read-only seam) and routes each through the run-failure
   reactor in **file-only** mode. One verdict line per routed incident (`TRIAGE-MAIN …` /
   `TRIAGE-PR …`); `MONITOR-OK` routes nothing. New target `make ci-monitor-triage`
   (`DRY=1` previews without writing).
2. `scripts/run_failure_reactor.py` gains `--file-only`: a Route-A (pushable PR head) run is filed
   as the same marker-deduped Route-B issue instead of dispatching the fix-bot. Host triage files
   issues and dispatches NOTHING — fix-bot dispatch stays a CI/human action.
3. The single sanctioned host cron job moves to profile `llgenie-planner` (same
   `~/.hermes/scripts/llgenie_ci_monitor.py` gate, same prompt contract); the maintainer-profile job
   is paused. There remains exactly one live host scheduler entry.
4. `AGENTS.md`'s monitor contract and `agents/llgenie-planner/` carry: the tick runs
   `make ci-monitor-triage` FIRST; a lane whose CI is in flight never idles the agent — it works the
   next open board issue meanwhile; a failed PR pipeline is fixed BY ITS LANE OWNER with pushed
   commits on the branch (the triage issue tracks main reds and failures no open lane owns).

## Impact

- Affected specs: `host-ci-monitor` (modified + added), `run-failure-reactor` (added)
- Affected code: `scripts/ci_monitor.py`, `scripts/run_failure_reactor.py`, `mk/bots.mk`,
  `Makefile` `.PHONY`, `scripts/package-layers.json`, tests for both scripts
- Affected agent trees: `AGENTS.md` (monitor contract), `agents/llgenie-planner/` (folded live↔tree)
- Host side (post-merge): monitor cron job recreated on the planner profile, maintainer copy paused
