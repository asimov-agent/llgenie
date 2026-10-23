# Tasks

- [x] 1. `tests/top_tier_dry_run.py` defines `TOP_TIER_DRY_RUN_ATTEMPTS = 2` and `run_dry_run`, retrying only a Hub transport failure
- [x] 2. Both dry-run cases in `tests/test_top_tier_acceptance.py` run through `run_dry_run`, and their zero-exit assertion names the attempt count and the cause
- [x] 3. `tests/test_top_tier_dry_run_retry.py` proves with real child processes: retry-once-then-pass, loud failure at the bound, no retry for a non-transient failure, and the measured `TimeoutError` shape is transient
- [x] 4. `README.md` states the dry-run retry bound and the loud-failure rule
- [x] 5. `agent-wiki/2026-10-23-top-tier-dry-run-transient-retry.md` names issue #399 and the PR
- [x] 6. `python3 -m pytest tests/test_top_tier_dry_run_retry.py -q` passes on the host (8 passed)
- [x] 7. The lint gate's own command (`python3 scripts/lint_linefeeds.py`) exits 0 and `make check-workflows` exits 0
- [x] 8. The full hermetic suite (`python3 scripts/unit_tests.py run`, the command `make test-unit` invokes) is green: 5069 passed, 6 deselected
- [x] 9. `make test-top-tier` (the target that runs the changed acceptance file) is green: 15 passed
- [x] 10. `make openspec-validate NAME=top-tier-dry-run-transient-retry` exits 0 (`Change … is valid`) with the pinned CLI 1.10.0
