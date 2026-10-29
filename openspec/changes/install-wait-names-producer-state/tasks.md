# Tasks

- [x] 1. `wait_published` reads the producer cell's own job state
      (`scripts/install_engine_launchers.py::producer_job_states`, joining on
      `engine-image-<engine>-<variant>` via `GET /actions/runs/<id>/jobs`), and classifies it as
      `queued` / `done` / `failed` / `unknown`
- [x] 2. A `queued`/`in_progress` producer keeps the wait alive to `PUBLISH_WAIT_QUEUE_MAX_S`
      (75 min) and then fails as `BLOCKED`, naming the cell and the queue as the cause
- [x] 3. A concluded producer shortens the wait to `PUBLISH_WAIT_CONCLUDED_GRACE_S` (2 min — a
      manifest can lag its own push) and then fails as `NOT FOUND`, naming the cell and its
      conclusion (success or failure)
- [x] 4. No readable state keeps the 30-minute budget and says the runner queue cannot be ruled
      out, instead of asserting the tag was never published
- [x] 5. `.github/workflows/pipeline.yml`: `install` gains `actions: read`, and its
      `timeout-minutes: 120` must exceed `PUBLISH_WAIT_QUEUE_MAX_S + PUBLISH_WAIT_RESERVE_S`
- [x] 6. `tests/test_ci_publish_order.py`: the six behaviour tests above, the API-name join, the
      no-lookup-on-published path, and the ceiling/permission checks — all hermetic (`# Given /
      # When / # Then` markers, an injected state, and an autouse fixture that strips
      `GITHUB_RUN_ID`/`GITHUB_TOKEN` so no unit test reaches the live API)
- [x] 7. Red-then-green control: `PUBLISH_WAIT_QUEUE_MAX_S = 30 * 60` reds the queued-past-the
      -old-budget test (reproducing #893's log); collapsing the `queued` verdict into the old
      "never published" text reds the BLOCKED test; restored head is 20 passed
- [x] 8. `docs/BOTS.md` + `docs/ENGINES.md` state the two verdicts; `agent-wiki/2026-10-29-install
      -wait-names-the-queue.md` records the change and `CHANGES.md` indexes it
- [x] 9. `make check-workflows check-docs check-wiring check-dispatch-forms lint
      openspec-tasks-check` exit 0 on the branch, and `make openspec-validate
      NAME=install-wait-names-producer-state` exits 0
