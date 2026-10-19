# Tasks

- [x] 1. Makefile: ONE `AGENT_SHELL_KEYS` list (every credential a container receives) + host-only export of `_HERMES_FORCE_<NAME>` from `<NAME>` by reference (nothing re-created when `/.dockerenv` is present) + `AGENT_SHELL_FORWARD`/`AGENT_SHELL_FORWARD_PLAIN`, and every agent leg (7) forwards the forced names by NAME
- [x] 2. `scripts/agent_shell_keys_check.py`: probe Hermes's REAL terminal environment (`LocalEnvironment`) and fail, naming the variable, when a container credential reads empty in the agent's shell — lengths only, exit 2 for a missing key or a missing Hermes, `--allow-unconfigured` as the only opt-out
- [x] 3. Makefile: `_agent-shell-keys-check` (internal) + `agent-shell-keys-check` (public, `$(RUNTIME) run` inside the agent image), `.PHONY`, `##` help line, `AGENT_SHELL_CHECK_KEYS` default = `AGENT_SHELL_KEYS`
- [x] 4. `.github/workflows/fix-bot.yml`, `issue-bot.yml`, `issue-refiner.yml`, `rebase-bot.yml`: one `make agent-shell-keys-check` step before the agent work, narrowed to the keys that job sets, and no workflow uses `--allow-unconfigured`
- [x] 5. `tests/test_agent_shell_keys.py`: the list covers every credential an agent leg forwards; the forced names travel by NAME (sentinels never in `make -n` output); the host export and the container no-op; the missing-key loudness and the opt-out; the wiring to the bot workflows — wired into `make test-unit`
- [x] 6. Verified against the REAL Hermes on this host: plain `-e NAME` → `agent-shell=EMPTY`, exit 1; `_HERMES_FORCE_<NAME>` → `agent-shell=set`, exit 0 (commands recorded in `README.md`); inside the agent image the same check is the bot jobs' new step (no PR-triggered job can pull an agent image a push run has not published, #155)
- [x] 7. `AGENTS.md`: the durable rule — credentials reach the agent's shell only through `AGENT_SHELL_KEYS` + the `_HERMES_FORCE_` seam
- [x] 8. `README.md`: the target and the seam documented in their own section, plus the bot-command list
- [x] 9. `agent-wiki/2026-10-19-agent-shell-keys.md`: the work record (issue #358 + the PR it opens)
- [x] 10. Verification: `make check-wiring`, `make check-docs`, `make check-secret-output`, `make check-workflows`, `make check-dispatch-forms`, `make lint`, `python3 -m pytest tests/test_agent_shell_keys.py` (7 passed), `make openspec-validate NAME=agent-shell-keys` (valid) — all green
