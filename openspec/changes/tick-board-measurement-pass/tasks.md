# Tasks — tick-board measurement pass (issue #2159)

- [x] Version `tick_board.sh` under `agents/llgenie-planner/scripts/` printing sections A–G in fixed order
- [x] Capture the running orchestrator prompt verbatim under `agents/llgenie-planner/cron/llgenie-orchestrator-tick.md` (13,044 b, `STEP 1…STEP 13`, a `Quote:` line per step, STEP 6 HOW TO DELEGATE, red-PR priority, no forward references)
- [x] Version `delegate.sh` under `agents/llgenie-planner/scripts/` as the one-command dispatch (validates brief, FATALs missing brief, refuses duplicate vehicle, creates, dispatches, CONFIRMS by reading the board back — running / ready-queued / BLOCKED; default `--message` makes skipping the message_agent send loud)
- [x] Add the `make check-tick-prompt` divergence gate (reds when live jobs.json prompt diverges from the versioned copy, naming both byte counts) with a hermetic test
- [x] Add hermetic tests: `test_tick_board.py` (A–G order + 2026-11-08 reproduction stale=12 dirty=2 idle_non_planner=7), `test_check_tick_prompt.py` (drift gate match/divergence/missing-job), `test_delegate.py` (incomplete brief, missing brief, duplicate refused, dry-run, three confirmation states, message-required)
- [x] Open the ready-for-review PR closing #2159
