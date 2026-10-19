# Tasks

- [x] 1. `AGENT_SHELL_KEYS` gains `FIRECRAWL_API_KEY`, so `make agent-shell-keys-check` proves the agent's shell can see it (the #358 seam, merged as #365)
- [x] 2. Makefile: `agent-fetch` (public) + `_agent-fetch` (the prompt: key read from the environment, never printed, writes only `OUT`, fails on 401/402/403) — the ONE fetch leg; `.PHONY`, `##` help lines
- [x] 3. Makefile: `search-smoke` running `scripts/fetch_smoke.py` inside the agent image with the key forwarded by name
- [x] 4. `scripts/fetch_smoke.py`: key by name, one bounded request, loud 401/402/403 with the code, an empty 200 refused, `--budget` bounds the kept markdown, missing key exit 2, `--allow-unconfigured` the only opt-out
- [x] 5. `tests/test_agent_web_reach.py` (9 tests, in `make test-unit`): the list + by-name forwarding, the prompt's no-print rule, the targets, and the smoke driven by the REAL client against a local server (401 / empty 200 / real body / budget / missing key)
- [x] 6. `tests/fixtures/host-only-wiring.json`: record why `search-smoke` is human-run (the repo has no `FIRECRAWL_API_KEY` secret yet; a missing key is exit 2 by design)
- [x] 7. `AGENTS.md` (one leg, keyed by name), `README.md` section, `agent-wiki/2026-10-19-agent-web-reach.md`
- [x] 8. Verification: `pytest tests/test_agent_web_reach.py` (9 passed), `make check-wiring`, `make check-docs`, `make check-secret-output`, `make check-workflows`, `make lint`, `make openspec-validate NAME=agent-web-reach`
