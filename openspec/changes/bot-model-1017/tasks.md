# Tasks

- [x] 1. `scripts/agent_model_pin.py`: the pin declared once (`MODEL_ID`, `MAX_TOKENS`, `CONTEXT_WINDOW`) with `check` (naming file + value on drift, non-zero) and `report`
- [x] 2. `containers/agent/Dockerfile`: `ARG HERMES_MODEL_ID` default -> `deepseek/deepseek-v4.1-flash-1017` (header too), and the build asserts `.model` / `.max_tokens` / `.context_window`
- [x] 3. `scripts/install_hermes_ci.sh`: same pin, writes `max_tokens` + `context_window` on the alias, and its loud post-write check covers all three keys
- [x] 4. `Makefile`: `check-agent-model` + `model-pin-report`, both `.PHONY`, and `ci-unit` runs the check
- [x] 5. `tests/test_agent_model_pin.py` (new) + `tests/test_issue_implementer.py` exact-id assert: drift in each file is a finding, the committed tree is green, the gate is reached by `ci-unit`
- [x] 6. `README.md` documents the pin, the gate and how to move it; `agent-wiki/2026-10-20-bot-model-1017.md` records the work with issue #405 and the PR
- [x] 7. Verified for real: `make check-agent-model`, `make test-unit`, the agent image rebuilt with the new pin, and a live `make hermes-smoke` answering through `-m nous-deepseek` on this snapshot
