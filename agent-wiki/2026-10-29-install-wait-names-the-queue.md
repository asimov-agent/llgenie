# The install wait names the queue, not a missing tag

Issue #893, implemented by PR #941 (branch `fix/893-install-waits-queue`). Related: #169 (the
wait itself), #872 (a ceiling interacting with the queue instead of with the work).

## What was wrong

`linux / install` pulls the images its own run is publishing in the parallel
`engine-image-<engine>-<variant>` cells. `make ci-wait-engine-images` polled the registry for
30 minutes and then failed with `… was never published`, which is true and misleading: on
#893 the four producer cells were still `pending` when the budget ran out, so the tag was
absent because the BUILDER had not started. A supply delay was filed as a red PR, and the
board read it as a bad pin. The job log confirmed 90 polls × 20 s = the whole budget spent.

## What changed

`scripts/install_engine_launchers.py::wait_published` now joins each absent tag to its
producer cell by the exact job name `ci.yml` sets, and reads that cell's state from the
Actions API (`GET /repos/<repo>/actions/runs/<run_id>/jobs?filter=latest`, token from
`GITHUB_TOKEN`; the `install` job gained `actions: read` for exactly this):

| producer state | what the wait does | the verdict |
|---|---|---|
| `queued` / `in_progress` | keeps waiting, up to `PUBLISH_WAIT_QUEUE_MAX_S` (75 min) | `BLOCKED — … still queued after N minutes with no runner: this is the runner queue, not a bad tag` |
| `completed/failure` | waits out a 2-minute grace, then fails | `NOT FOUND — the producer cell … concluded failure` |
| `completed/success` | waits out a 2-minute grace, then fails | `NOT FOUND — … concluded success and <ref> was never published` (the pin / publish step needs a look) |
| nothing readable (host run, no `actions: read`) | the old 30-minute budget | `NOT FOUND — … the runner queue cannot be ruled out` |

The decisions worth recording:

- **The producer's own state is the referee, not a longer timeout.** Raising 30 → 75 minutes
  alone only moves the cliff; what makes the log honest is that a concluded producer ends the
  wait and a live one extends it. A `completed/success` cell whose tag is missing is the only
  case that is genuinely a bad tag.
- **A concluded producer shortens the budget to a two-minute grace, not to zero.** A registry
  manifest can lag the push that created it (or answer 404 while the token is minted), and a
  verdict taken at zero would be a flake wearing a defect's clothes —
  `PUBLISH_WAIT_CONCLUDED_GRACE_S` keeps the retries while removing the 30-minute sit.
- **Nothing is skipped.** No job-level or step-level `if:` was added, so
  `test_no_ci_step_or_job_is_skipped` still sees the same shape; `install` reports exactly as
  before, and only the *text and the waiting* changed.
- **Both bounds are finite and related to the job's ceiling.** 75 min of wait + the 20-minute
  reserve (`PUBLISH_WAIT_RESERVE_S`) for the pull/install/dry-run/uninstall stays under
  `install`'s `timeout-minutes: 120`. `test_the_queue_ceiling_fits_inside_the_install_job_timeout`
  reads the workflow file, so lowering the job ceiling or raising the wait reds the suite.
- **The fallback is loud about what it cannot know.** With no readable state the message says
  the queue cannot be ruled out rather than re-asserting "never published".
- **The permission belongs on BOTH sides of a reusable workflow.** Granting `actions: read` only
  in `pipeline.yml`'s `install` job made GitHub refuse the entire workflow at load time: the run
  came back `completed / startup_failure` with **0 jobs** and `gh run view --log-failed` answers
  "log not found", which reads like a broken branch rather than a rejected file (measured: run
  `40819108106` at head `b82eef8`). A called workflow can never grant more than its caller passes,
  so `ci.yml`'s `linux` job grants `actions: read` too, and
  `test_the_caller_grants_the_action_read_the_callee_needs` walks every caller of the reusable
  pipeline so the pair cannot drift again.
- **The API call is never on the happy path.** An already-published image returns on the first
  poll without a single lookup (pinned by `test_published_images_never_consult_the_producer_state`).

## How it was proven

`tests/test_ci_publish_order.py` (21 tests, hermetic — the Actions lookup is injected and an
autouse fixture strips `GITHUB_RUN_ID`/`GITHUB_TOKEN` so a unit test can never read the live
API). Two mutations were run and reverted:

1. `PUBLISH_WAIT_QUEUE_MAX_S = 30 * 60` (the retired budget) → the queued-past-the-old-budget
   test goes red (`1 failed, 20 passed`), reproducing #893's log verbatim (the wait reports
   "keeping the wait alive up to 30 minutes" and then `BLOCKED` at 30).
2. collapsing the `queued` verdict into the old "never published" text → the BLOCKED test goes
   red (`1 failed, 20 passed`), so the two-cause contract is guarded, not just written down.

Restored head: `21 passed` (and `47 passed` together with `tests/test_ci_images.py`). The
negative control the issue asked for is
`test_a_producer_that_concluded_success_with_a_missing_tag_fails_as_NOT_FOUND` (a genuinely
missing tag still fails) plus `test_a_producer_that_failed_ends_the_wait_at_the_grace_period`.
