# Tasks

- [x] 1. `scripts/require_env.py`: name-only messages, exit 2 on the first missing/empty variable, bad names refused, no value/prefix/length printed
- [x] 2. Makefile: `require-env KEYS="…"` (public) + the guard as the FIRST recipe line of every agent leg, ahead of `scripts/ci_images.py ensure agent` (`rebase-bot-agent`, `issue-refiner`, `issue-bot-triage`, `agent-jev-preflight`, `implement-issue`, `hermes-smoke`, `fix-loop-image`, `agent-shell-keys-check`); `.PHONY`, `##` help line
- [x] 3. Makefile: the ad-hoc `test -n "$$NOUS_API_KEY"` guard replaced by the script in `hermes-smoke` AND `_hermes-smoke` (one code path)
- [x] 4. `tests/test_require_env.py` in `make test-unit`: missing/empty/present/name cases, and the wiring — roster derived from the Makefile, guard before the image pull, the old bash guard gone
- [x] 5. `AGENTS.md` ("before the image, not inside it") + `README.md` section + `agent-wiki/2026-10-19-require-env-guard.md`
- [x] 6. Verification: `pytest tests/test_require_env.py tests/test_agent_shell_keys.py` (14 passed), `make check-wiring`, `make check-docs`, `make check-secret-output`, `make lint`, `make openspec-validate NAME=require-env-guard`
