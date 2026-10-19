# Tasks

- [x] 1. Confirm the `FIRECRAWL_API_KEY` repository secret exists (owner action, set 2026-10-19T21:02Z) — `gh api repos/asimov-agent/llgenie/actions/secrets` lists it
- [x] 2. `.github/workflows/search-smoke.yml`: its own cron slot (daily 07:11 UTC), the shared byte-identical trigger guard, `FIRECRAWL_API_KEY` by name, the agent-shell check ahead of `make search-smoke`
- [x] 3. `tests/fixtures/host-only-wiring.json`: delete the `search-smoke` exception (stale the moment CI reaches it)
- [x] 4. `tests/test_agent_web_reach.py`: the workflow's shape (slot, header, key by name, check before the smoke), and the exception is gone
- [x] 5. `tests/test_workflow_guards.py`: the guard-site count is derived from the workflow files, not the literal `11`
- [x] 6. `README.md`: the web-reach section says where the smoke runs; the generated dispatch table is refreshed (`make dispatch-forms-report`)
- [x] 7. `agent-wiki/2026-10-19-firecrawl-ci-smoke.md`: the work record, referencing #381 and PR #384
- [x] 8. Verification: `make test-unit` (4807 passed, 3 deselected), `make check-workflows`, `make check-wiring`, `make check-dispatch-forms`, `make check-docs`, `make check-secret-output`, `make lint`, `make openspec-validate NAME=firecrawl-ci-smoke` — all green

The live proof of the secret's VALUE is the merged job itself: the scheduled `search-smoke.yml` run (or
a hand dispatch) is read after the merge, and a failure there is the loud signal this change buys.
