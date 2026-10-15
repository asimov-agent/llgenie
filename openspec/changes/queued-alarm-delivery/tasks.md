# Tasks

- [x] 1. `scripts/queued_run_alarm.py` delivers the report to a real subject: the PR the run's HEAD BRANCH belongs to (the REST `pull_requests` array is empty for fork-PR runs, and `gh run view --json` has no `pullRequests` field — both measured live), else ONE deduped issue per stuck label; the run-id URL is gone
- [x] 2. Dedupe markers name their subject (`run <id>` / `label <label>`), `--dry` posts nothing, and every delivery checks its return code
- [x] 3. A failed delivery is loud: `DELIVERY FAILED: …` on stderr and exit 3 (read failure stays 2, stuck-without-delivery stays 1)
- [x] 4. `tests/test_queued_run_alarm.py`: the PR target (and that `/issues/<run id>` is never called), the per-label fallback + its dedupe, the loud failure, `--dry`, and the marker contract; the old test that pinned the run-id URL is replaced
- [x] 5. Falsified: the new tests fail on the pre-fix script (`6 failed, 11 passed`) and pass on the fixed one (`17 passed`) in `llgenie/test:latest`
- [x] 6. `make queued-alarm DRY=1` / `COMMENT=1` wired, the help line and the README say where the report lands, and the workflow step is named for the delivery
- [x] 7. `make openspec-validate NAME=queued-alarm-delivery`, `make lint`, `make check-docs` and `make check-wiring` exit 0 on the branch; `agent-wiki/2026-10-15-queued-alarm-delivery.md` records the work
