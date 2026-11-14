# Tasks: planner-cron-store-restore-2653

- [x] 1. Root-cause the 2026-11-11 wipe from evidence (update receipts, gateway
      drain/hard-interrupt log lines, the empty-document stamp vs healthy-save
      offsets, `load_jobs` empty-coercion, restore-net silence) and record it in
      `agent-wiki/2026-11-14-planner-cron-store-restore-2653.md`
- [x] 2. Restore the live orchestrator tick job `cc5d2bd4083a` in
      `~/.hermes/profiles/llgenie-planner/cron/jobs.json` with pinned id and the
      byte-identical committed prompt (30m interval, `deliver: local`, skill
      `llgenie-bot-orchestration`, toolsets terminal+skills)
- [x] 3. `make check-tick-prompt` exits 0 (live prompt == versioned)
- [x] 4. Arm one live tick dispatch (`hermes cron run cc5d2bd4083a`) and read the
      durable run id from `hermes cron runs cc5d2bd4083a`
- [x] 5. `make check-cron-drift` confirms its ONLY remaining findings are the two
      sweeper prompts that #2654 changes and has not landed on main yet (the gate's
      own "review not landed" state); the post-#2654 replay is issue AC4, tracked on #2653
- [x] 6. Add the `docs/changes.d` row; tick the issue's acceptance criteria with
      replayable proven strings
- [x] 7. Verification replay: at the lane head run `make check-tick-prompt` (rc=0) and
      `make openspec-validate NAME=planner-cron-store-restore-2653` (valid); the
      `check-cron-drift` clean replay is issue AC4, lands with #2654
