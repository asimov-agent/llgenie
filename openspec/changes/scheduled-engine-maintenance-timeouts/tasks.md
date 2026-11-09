# Tasks

- [x] 1. The four scheduled step jobs carry `timeout-minutes`: `engine-bump.yml` `plan`=20, `bump`=30; `engine-bump-rebase.yml` `rebase`=20; `registry-sync.yml` `sync`=60 (measured from real runs, per `proposal.md Technical`)
- [x] 2. `scripts/check_workflows.py` gains `check_scheduled_job_timeouts`: every non-`uses` job of a `schedule`-triggered workflow must declare `timeout-minutes`, wired into `findings()` and the `render` summary
- [x] 3. `tests/test_workflows_valid.py` adds five cases: scheduled-no-timeout → reported; scheduled-with-timeout → accepted; non-scheduled workflow → out of scope; scheduled `uses:` job → skipped (#882); repro-tree → green
- [x] 4. Negative control proven on the PR head: removing `sync`'s 60 reds `make check-workflows` (rc=1, names `registry-sync.yml`/`sync`) and fails the repro-tree test; restoring returns green (numbers quoted in the PR body)
- [x] 5. `agent-wiki/2026-11-09-scheduled-engine-timeouts-2317.md` + `docs/changes.d/2026-11-09-scheduled-engine-timeouts-2317.md` record the change (issue #2317, the PR), and `make changes-index` re-renders `CHANGES.md`
- [x] 6. Gates green: `make lane-preflight` → `preflight: OK (6 gate(s))`; `python3 -m pytest tests/test_workflows_valid.py tests/test_engine_build_timeouts.py tests/test_pipeline_timeouts.py tests/test_engine_bump_rebase.py tests/test_registry_sync_trend.py tests/test_code_review.py tests/test_issue_bot_gates.py tests/test_pr_hygiene.py` → 128 passed
- [x] 7. `make openspec-validate NAME=scheduled-engine-maintenance-timeouts` passes, and `make openspec-tasks-check` is green
