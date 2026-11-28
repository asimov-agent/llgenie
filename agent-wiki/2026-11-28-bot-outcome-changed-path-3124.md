# Bot outcome changed-path backstop (issue #3124)

Branch `agent/issue-3124-bot-outcome-backstop`, cut from freshly fetched `origin/main@d5858e8615cb780858bef441cb48d4ae46ab9436`.

## What changed

- `scripts/check_bot_outcome.py verify-changed-path` exits non-zero when there is no durable changed artifact: the post-head equals the pre-head, no `agent/issue-<n>-*` branch on origin matches the issue, and no PR names it. An unrelated issue branch is not evidence.
- An empty PR/issue body and a session that was never created are vacuous and count as no changed path, even when a head moved.
- `make verify-bot-outcome` is the shared seam; every bot outcome step that writes a `bot-done … fixed` marker calls it BEFORE that step (subset assertion in tests, so a new bot inherits the guard). The helper only adds a failure mode; no existing gate was weakened.
- Root causes #3121, #3123 and #3120 stay with their owners; this is the shared backstop they will call.

## Verification

`pytest tests/test_check_bot_outcome.py -q` (8 passed), `make check-workflows`, `make openspec-validate NAME=bot-outcome-changed-path-3124`, `make -s check-docs`.

## Not covered

- Per-bot triage/skill wiring (#3121), fix-bot live-body fetch (#3123), planner audit counts (#3120).
- No merge, no arm, no self-tick (#1088/#1644).
