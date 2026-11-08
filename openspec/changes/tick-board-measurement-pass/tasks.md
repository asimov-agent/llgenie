# Tasks — tick-board measurement pass (issue #2159)

- [x] Version `tick_board.sh` under `agents/llgenie-planner/scripts/` printing sections A–G in fixed order
- [x] Capture the running orchestrator prompt verbatim under `agents/llgenie-planner/cron/llgenie-orchestrator-tick.md`
- [x] Add host-only `make check-tick-prompt` that reds when the live jobs.json prompt diverges from the versioned copy
- [x] Add hermetic tests pinning the A–G order and the 2026-11-08 reproduction (stale=12 dirty=2 idle_non_planner=7)
- [x] Open the ready-for-review PR closing #2159
