# Tasks

- [x] 1. `.github/workflows/issue-bot.yml`: the implement job's `env:` gains `GH_TOKEN: ${{ github.token }}`, with the comment that explains why (the leg forwards it; the PUSH still uses the owner PAT)
- [x] 2. `.github/workflows/issue-bot.yml`: `AGENT_SHELL_CHECK_KEYS` gains `GH_TOKEN`, so #358's probe proves the agent's shell sees it
- [x] 3. `tests/test_agent_shell_keys.py`: the step-scoped rule — for each bot workflow, the step that runs the leg must export every key the leg forwards (a sibling step's env does not count); plus a synthetic fixture proving the detector fails the #364 shape
- [x] 4. Demonstrated RED/GREEN against the real file: pre-fix `step sees GH_TOKEN: False`, post-fix `True`
- [x] 5. `README.md` note + `agent-wiki/2026-10-19-issue-bot-ghtoken.md`
- [x] 6. Verification: `pytest tests/test_agent_shell_keys.py` (9 passed), `make check-wiring`, `make check-docs`, `make check-secret-output`, `make check-workflows`, `make lint`, `make openspec-validate NAME=issue-bot-ghtoken`
