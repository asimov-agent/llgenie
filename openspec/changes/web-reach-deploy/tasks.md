# Tasks

- [x] 1. `scripts/web_evidence.py`: extract candidates, `check` a URL list (non-zero on a dead one, 401/403 reachable), and `fetch` through the REAL `make agent-fetch` with a cap; the index records a failure as UNKNOWN
- [x] 2. `tests/fixtures/bot-facing-urls.md`: the declared dependency list `make web-coverage` checks with no issue
- [x] 3. `Makefile`: `web-coverage` + `issue-evidence` targets, both `.PHONY`, and `issue-refiner` runs the agent-shell credential check first, then the pre-fetch, then the review
- [x] 4. `.github/workflows/issue-refiner.yml` forwards `FIRECRAWL_API_KEY` by NAME and covers it in the job's keys check; `.github/workflows/search-smoke.yml` runs `make web-coverage` daily; `.gitignore` ignores `fetched/`
- [x] 5. `tests/test_agent_web_reach.py`: the derived wiring assertion (`agent-fetch` reached through `issue-evidence`), the leg's gate order, candidate extraction, the dead-URL failure, and the 401/403 classifier
- [x] 6. `README.md` documents both targets and the leg order; `agent-wiki/2026-10-20-web-reach-deploy.md` records the work with issue #380 and the PR
- [x] 7. Verification: `make web-coverage` (4/4 reachable; a 404 exits non-zero), `pytest tests/test_agent_web_reach.py` (16 passed), `make check-wiring`, `make check-docs`, `make check-workflows`, `make check-secret-output`, `make check-dispatch-forms`, `make lint`, `make openspec-validate NAME=web-reach-deploy`, `make test-unit`
