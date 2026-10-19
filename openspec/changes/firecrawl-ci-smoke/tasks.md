# Tasks

- [ ] 1. Confirm the `FIRECRAWL_API_KEY` repository secret exists (owner action, 2026-10-19) — `gh api repos/asimov-agent/llgenie/actions/secrets`
- [ ] 2. `.github/workflows/search-smoke.yml`: its own cron slot (daily 07:11 UTC), the shared trigger guard, `FIRECRAWL_API_KEY` by name, the agent-shell check ahead of `make search-smoke`
- [ ] 3. `tests/fixtures/host-only-wiring.json`: delete the `search-smoke` exception (stale the moment CI reaches it)
- [ ] 4. `tests/test_agent_web_reach.py`: the workflow's shape (slot, header, key by name), and the exception is gone
- [ ] 5. `README.md`: the web-reach section says where the smoke runs; the generated dispatch table is refreshed (`make dispatch-forms-report`)
- [ ] 6. `agent-wiki/2026-10-19-firecrawl-ci-smoke.md`: the work record, referencing #381 and the PR
- [ ] 7. Verification: `make check-workflows`, `make check-wiring`, `make check-dispatch-forms`, `make check-docs`, `make check-secret-output`, `make test-unit`, `make openspec-validate NAME=firecrawl-ci-smoke`
- [ ] 8. The scheduled job proves the secret's VALUE end to end: dispatch `search-smoke.yml` after merge and read the run's result
