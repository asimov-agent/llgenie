# ci-engine-images

## ADDED Requirements

### Requirement: an absent engine-image tag names WHICH cause it has

When `make ci-wait-engine-images` finds a tag that `install` will pull absent, it MUST
distinguish a producer cell that has not run yet from one that has concluded, and MUST NOT
report a runner-queue delay as a missing image.

#### Scenario: a producer that is still queued keeps the wait alive
- **Given** a CI run whose `engine-image-<engine>-<variant>` cell is `queued` (or `in_progress`)
  and whose registry tag is therefore not published yet
- **When** the install job's wait polls the registry past its 30-minute budget
- **Then** the wait keeps polling, up to `PUBLISH_WAIT_QUEUE_MAX_S`
- **And** it passes as soon as the cell publishes the tag
- **Test:** `tests/test_ci_publish_order.py::test_a_queued_producer_keeps_the_wait_alive_past_the_old_budget`

#### Scenario: a producer that is queued past the ceiling is reported as BLOCKED
- **Given** a producer cell that is still `queued` when the queue ceiling is reached
- **When** the wait gives up
- **Then** the failure line reads `BLOCKED — the producer cell <job> is still queued after N
  minutes with no runner: this is the runner queue, not a bad tag`
- **And** it never says the tag is missing
- **Test:** `tests/test_ci_publish_order.py::test_a_producer_queued_past_the_ceiling_fails_as_BLOCKED`

#### Scenario: a producer that concluded with a missing tag is reported as NOT FOUND
- **Given** a producer cell that has `completed`, and a tag that is still absent
- **When** the wait reads that state
- **Then** it shortens the budget to `PUBLISH_WAIT_CONCLUDED_GRACE_S` (a manifest can lag
  its own push, so the verdict is not taken at zero)
- **And** it then fails as `NOT FOUND`, naming the cell and its conclusion
- **And** a producer that concluded `failure` is likewise named, with the remedy that the
  producer cell — not the wait — needs the fix
- **Test:** `tests/test_ci_publish_order.py::test_a_producer_that_concluded_success_with_a_missing_tag_fails_as_NOT_FOUND`
  and `tests/test_ci_publish_order.py::test_a_producer_that_failed_ends_the_wait_at_the_grace_period`

#### Scenario: no readable producer state says the queue cannot be ruled out
- **Given** a host run, or a job whose token cannot read the run's jobs
- **When** the wait reaches its budget with a tag still absent
- **Then** it keeps the 30-minute budget and fails saying no producer state could be read
- **And** it states that the runner queue cannot be ruled out, instead of asserting the tag
  was never published
- **Test:** `tests/test_ci_publish_order.py::test_no_readable_producer_state_says_capacity_cannot_be_ruled_out`
  and `tests/test_ci_publish_order.py::test_the_producer_lookup_is_empty_outside_actions`

### Requirement: the wait's ceiling fits inside the install job's timeout

The install job's `timeout-minutes` MUST exceed the queue ceiling plus the reserve the rest of
the job needs, so a hung producer cannot inherit GitHub's six-hour default, and the job MUST be
allowed to read the run's jobs.

#### Scenario: the relation is pinned against the workflow file
- **Given** the `install` job declared in `.github/workflows/pipeline.yml`
- **When** the wait's constants are compared with its `timeout-minutes`
- **Then** `PUBLISH_WAIT_QUEUE_MAX_S + PUBLISH_WAIT_RESERVE_S` is strictly below that ceiling
- **And** the job's permissions carry `actions: read`
- **Test:** `tests/test_ci_publish_order.py::test_the_queue_ceiling_fits_inside_the_install_job_timeout`
  and `tests/test_ci_publish_order.py::test_the_install_job_may_read_the_producer_state`

### Requirement: an already-published image costs no Actions API read

The wait MUST NOT consult the producer cells' state when every tag it resolves is already
published.

#### Scenario: nothing to wait for means no lookup
- **Given** a registry that answers every resolved tag with a digest
- **When** the wait runs
- **Then** it returns success after one pass over the tags and never calls the job-state lookup
- **Test:** `tests/test_ci_publish_order.py::test_published_images_never_consult_the_producer_state`
  and `tests/test_ci_publish_order.py::test_published_images_need_no_wait`
