# Tasks — retire-ci-requeue (issue #2702)

- [x] 1. Delete `scripts/ci_requeue.py`, `tests/test_ci_requeue.py`, `.github/workflows/ci-requeue.yml`, `make ci-requeue-cancelled` (mk/ci.mk + Makefile .PHONY)
- [x] 2. Strip the lane from run_failure_reactor (PIPELINE_STEMS + pending-cancel message), fix_bot_sweep (pending message + comment), and their tests
- [x] 3. Re-point `zero-job-pending.yml`'s workflow_run roster onto ci-frozen-reaper; update the guard-derivation docstring in check_workflows.py
- [x] 4. Remove from inventories (package-layers.json, import-roots-baseline.json) and comments (ci_verdict, all_pipelines, bots_restore_health, ci_frozen_reaper, ci-frozen-reaper.yml, ci-hf-live.yml) + their tests
- [x] 5. Docs: BOTS.md row/target/paragraph (retirement note), ARCHITECTURE.md lists, changes.d fragment, agent-wiki entry naming #2702
- [x] 6. Gates green: `make check-wiring check-workflows check-docs check-ci-discipline check-agent-profiles-ratchet test-unit` rc=0 on the branch
