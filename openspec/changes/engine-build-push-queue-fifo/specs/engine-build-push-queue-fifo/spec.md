# engine-build-push-queue-fifo

## ADDED Requirements

### Requirement: a pending push build queues FIFO instead of being cancelled

When `engine-build.yml`'s shared `concurrency:` group governs push=true runs, a newer dispatch MUST
NOT cancel-and-replace an older pending run in the same group. The group MUST declare `queue: max`
beside `cancel-in-progress: false` so up to 100 pending runs wait FIFO and each reaches a terminal
verdict.

WHEN the `engine-build-push` concurrency group is read from `.github/workflows/engine-build.yml`
AND its `concurrency.queue` is parsed from the workflow map
THEN `queue == "max"`, so a pending push build is never superseded by the next dispatch.

#### Scenario: the shared push group queues pending runs

- **Given** `.github/workflows/engine-build.yml`'s `concurrency:` block with `group: engine-build-${{ inputs.push == 'true' && 'push' || … }}`
- **When** the parsed concurrency map is read by the pinned test
- **Then** `queue == "max"` and `cancel-in-progress` is false
- **Test:** `tests/test_ci_concurrency.py::test_engine_build_pending_push_queue_runs_fifo`
  parses the workflow and asserts the shared push group's `concurrency.queue == "max"` — a comment
  mentioning `queue:` alone cannot satisfy it (issue #2301).
