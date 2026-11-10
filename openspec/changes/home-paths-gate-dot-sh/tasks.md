# Tasks

- [x] 1. `scripts/check_agent_profiles.py` extends the home-path-literal scan to `agents/**/*.sh`, skipping `#` comment lines and keeping `scripts/*.py` excluded. Verified: the gate diff on PR #2441 (this branch); CI `ci-unit` runs the gate at this head
- [x] 2. `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/stack-replay.sh` fallback converted to `$HOME`. Verified: the script diff on this branch; gate re-scan green in CI `ci-unit`
- [x] 3. `tests/test_home_paths_gate.py` carries the new .sh scenarios (executed literal red, comment accepted). Verified: the test-module diff on this branch; runs in CI `ci-unit`
- [x] 4. Change note trio present (agent-wiki entry + docs/changes.d row naming #2436 and PR #2441). Verified: `make lint` OK at this head; `make check-docs` runs in CI
