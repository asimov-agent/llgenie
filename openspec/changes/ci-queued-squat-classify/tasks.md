# Tasks: ci-queued-squat-classify

- [x] 1. Write the proposal + spec (issue #2656): run-level orphan/expired classification,
      once-per-episode reporting, expiry-not-a-live-matrix, never-cancel.
- [x] 2. `scripts/queued_run_alarm.py`: `squat_runs` classifies orphan (404 head branch + no OPEN PR)
      vs expired (in_progress, all jobs concluded) vs live; `render_squat` and `episode_marker` and
      `file_squat_issue` (ONE deduped episode issue through `issue_body.render`); wired into `main`
      with the exit-code contract (1 on a squat, 3 on a failed delivery, never a cancel).
- [x] 3. Tests (`tests/test_queued_run_alarm.py`): orphan/live/open-PR/expired/live-in_progress
      classification, once-per-episode dedupe, never-cancel, episode marker sorted.
- [x] 4. Written handling rule for orphan-queued runs in `docs/BOTS.md`, gated on the owner's word
      for any cancellation.
- [x] 5. docs fragment + agent-wiki note + CHANGES.md row, referencing issue #2656.
- [x] 6. Verify: the queued-run-alarm test module green (`python3 -m pytest tests/test_queued_run_alarm.py`),
      the module imports, and the change structure matches the CLI output. (The OpenSpec CLI could not
      be executed in the agent container — no docker daemon and no node/npm — so `openspec validate`
      runs in CI's node-bearing environment; tasks 1-5 are hand-crafted to the CLI's canonical shape.)
