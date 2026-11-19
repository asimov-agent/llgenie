# Tasks: agent-model-catalog-check

- [x] Create this OpenSpec change (proposal + spec delta + tasks) before any code
- [x] Add `scripts/check_agent_model_catalog.py` (stdlib + yaml config read; public HTTP;
      `--catalog`/`--dry-run`; missing-id + budget-divergence findings; ONE deduped issue
      via `issue_body.render` with marker read-back; add producer to `issue_body.PRODUCERS`)
- [x] Wire `make check-agent-model-catalog` (mk/bots.mk + help line + docs/BOTS.md entry)
- [x] Add the weekly step to `.github/workflows/registry-sync.yml` (sync job, job-scoped
      GH_TOKEN) and update the `SCHEDULE_ALLOW` rationale for registry-sync.yml
- [x] Add `tests/test_check_agent_model_catalog.py` (fixture catalog: green run, missing id,
      budget divergence, dry-run body + marker, dedupe read-back via monkeypatched gh,
      registry-sync wiring + weekly cron intact, no-credential proof)
- [x] Register `check_agent_model_catalog` in `scripts/package-layers.json`; agent-wiki
      entry + `docs/changes.d/` fragment + `make changes-index`
- [x] Gates green at the final head: targeted pytest battery, `make check-ci-discipline`,
      `make check-wiring`, `make check-docs`, `make openspec-validate NAME=agent-model-catalog-check`,
      and a LIVE `make check-agent-model-catalog` rc=0 against the fetched catalog
- [x] Final alignment: issue #2930 body, PR body, and commit text mirror the same acceptance
      criteria with proven clauses; `make openspec-tasks-check` green
