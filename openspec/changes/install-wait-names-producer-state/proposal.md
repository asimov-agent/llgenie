# ci: the engine-image wait must name the runner queue, not a missing tag

Issue: [#893](https://github.com/asimov-agent/llgenie/issues/893) (related:
[#169](https://github.com/asimov-agent/llgenie/issues/169) — the wait itself,
[#872](https://github.com/asimov-agent/llgenie/issues/872) — a ceiling interacting with the
queue instead of with the work)

## Why

`linux / install` pulls the engine images that the SAME run is publishing in the parallel
`engine-image-<engine>-<variant>` cells. `make ci-wait-engine-images` polls the registry for
30 minutes and then fails with `… was never published`, which is true and misleading. On #893
the four producer cells were still `pending` when the budget ran out, and the job log confirms
the whole budget was honoured (90 polls × 20 s, 19:17:11 → 19:47:28) before the verdict. So a
supply delay — the runner queue — is reported as a red install, and the board reads it as a bad
pin. A timeout that reports the wrong cause is worse than no timeout.

## What Changes

- `scripts/install_engine_launchers.py::wait_published` joins every absent tag to its producer
  cell by the job name `ci.yml` sets (`engine-image-<engine>-<variant>`) and reads that cell's
  state from the Actions API (`GET /repos/<repo>/actions/runs/<run_id>/jobs?filter=latest`,
  token from `GITHUB_TOKEN`). The verdict now says which of the two causes it saw:
  - a producer that is `queued`/`in_progress` keeps the wait alive up to
    `PUBLISH_WAIT_QUEUE_MAX_S` (75 min) and then fails as `BLOCKED — the producer cell <job> is
    still queued after N minutes with no runner: this is the runner queue, not a bad tag`;
  - a producer that has CONCLUDED ends the wait at once and fails as `NOT FOUND`, naming the
    cell and its conclusion — that is the case where the tag genuinely is absent;
  - when no state can be read (a host run, or a token without `actions: read`) the old
    30-minute budget stands and the message says the runner queue cannot be ruled out.
- `.github/workflows/pipeline.yml`: the `install` job gains `actions: read` (it cannot read the
  run's jobs otherwise) and a comment stating the 75 + 20 < 120 relation its `timeout-minutes`
  must keep. `.github/workflows/ci.yml`: the `linux` job that CALLS the reusable pipeline grants
  `actions: read` too — a called workflow can never exceed its caller's token, and granting it in
  the callee alone made GitHub refuse the whole workflow at load time (`startup_failure`, 0 jobs).
- No job-level or step-level `if:` is added: nothing is skipped, and the `install` check name
  still reports exactly as before.
- `tests/test_ci_publish_order.py` pins all of it hermetically (the Actions lookup is injected;
  an autouse fixture strips `GITHUB_RUN_ID`/`GITHUB_TOKEN` so a unit test can never call the live
  API), including the ceiling/timeout relation read from the workflow file and the
  `actions: read` requirement.
- `docs/BOTS.md` and `docs/ENGINES.md` describe the two verdicts; the change record lives in
  `agent-wiki/2026-10-29-install-wait-names-the-queue.md` and is indexed in `CHANGES.md`.

## Impact

- `scripts/install_engine_launchers.py`, `.github/workflows/pipeline.yml`,
  `.github/workflows/ci.yml`,
  `tests/test_ci_publish_order.py`, `docs/BOTS.md`, `docs/ENGINES.md`, `CHANGES.md`,
  `agent-wiki/2026-10-29-install-wait-names-the-queue.md`
- No new make target, no change to which work CI does, no change to the merge gate.
