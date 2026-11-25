# pins-gate-ordering

## ADDED Requirements

### Requirement: an unresolved pin this PR repins is reported as pending, not as a failure

`make check-engine-pins-published` MUST report a repinned engine cell whose exact tag resolves no
registry manifest in one of two distinct states. In a PR lane it MUST report `PINS-PENDING <ref>` and
exit zero with a `PINS DEFERRED <n>` summary line — the lane's own producer job
(`engine-build-pr-trigger`) is still publishing that tag. Outside a PR lane (a `push`/`main` run) the
same cell MUST stay `NOT PUBLISHED <ref>` with its `[select]` line and a non-zero exit. The mode is
read from `ENGINE_PINS_PR_PENDING` (`1`/`true` on, `0`/`false`/empty off, any other value warns on
stderr and stays off); when the knob is unset the gate falls back to `GITHUB_EVENT_NAME` and defers
only for `pull_request`. A lagging `:<variant>` arch alias or engine `:latest` of a repinned cell MUST
be reported `ALIAS-PENDING <ref>` under the same scope and exit rules.

#### Scenario: a bump PR defers the pins it is still producing

- **Given** a change that repins an engine cell whose exact tag resolves no manifest
- **And** the gate runs with `ENGINE_PINS_PR_PENDING=1`
- **When** `make check-engine-pins-published` runs
- **Then** it prints `PINS-PENDING <ref>` and `PINS DEFERRED 1`
- **And** it prints no `NOT PUBLISHED` line and no `[select]` line for that ref
- **And** it exits zero
- **Test:** `tests/test_check_engine_pins_published.py::test_pr_lane_defers_a_repinned_ref_its_producer_has_not_published`

#### Scenario: the same unresolved pin stays red outside a PR lane

- **Given** the same unresolved repinned cell
- **And** the gate runs with `ENGINE_PINS_PR_PENDING=0` and no `pull_request` event
- **When** `make check-engine-pins-published` runs
- **Then** it prints `NOT PUBLISHED <ref>` and the `[select]` line
- **And** it exits non-zero
- **Test:** `tests/test_check_engine_pins_published.py::test_main_lane_keeps_the_hard_red_for_the_same_unpublished_ref`

#### Scenario: the event fallback defers only in a PR lane

- **Given** the knob is unset
- **When** the gate runs with `GITHUB_EVENT_NAME=pull_request`
- **Then** the unresolved repinned pin is `PINS-PENDING` and the exit is zero
- **And** with `GITHUB_EVENT_NAME=push` the same pin is `NOT PUBLISHED` and the exit is non-zero
- **Test:** `tests/test_check_engine_pins_published.py::test_pending_mode_comes_from_the_pr_event_when_the_knob_is_unset`

### Requirement: pending scope never hides a gap the change did not repin

The pending state MUST cover only the cells THIS change repins. A cell that is unresolved and was not
repinned by the change MUST stay hard red in a PR lane exactly as on `main`, and the committed-fleet
sweep (`make check-engine-pins-valid`, `--all`) MUST never defer: every finding there stays
`NOT PUBLISHED` / `ALIAS LAG` with a non-zero exit whatever the event.

#### Scenario: a pre-existing publish gap reds the PR lane

- **Given** a PR lane (`ENGINE_PINS_PR_PENDING=1`) whose change repins no engine
- **And** a committed cell's tag resolves no manifest
- **When** the gate runs with `ALL=1`
- **Then** it prints `NOT PUBLISHED` for that cell
- **And** it prints no `PINS-PENDING` line
- **And** it exits non-zero
- **Test:** `tests/test_check_engine_pins_published.py::test_the_committed_sweep_never_defers_even_in_a_pr_lane`

### Requirement: the PR lane awaits its own image producer before the pins step

`make engine-pins-await` (`scripts/engine_pins_await.py`, wired in `mk/engines.mk`) MUST read — read-
only — the `engine-build-pr-trigger` run(s) for the current head via `gh api`, print
`AWAIT <run_id> <status>` per producer run, poll until each concludes or the bounded window
`ENGINE_PINS_AWAIT_SECONDS` (default 0, so an unconfigured call never waits) expires, and exit zero in
every outcome including "nothing this change repins". It MUST NOT dispatch, re-trigger, re-run or
cancel any workflow. In `.github/workflows/pipeline.yml`, the `unit` job (the job `ci.yml`'s `linux`
lane calls) MUST run that await step BEFORE the step that runs `make ci-unit`, so the battery's pins
step is evaluated after the lane's producer has concluded or the window closed.

#### Scenario: the await polls the producer and returns

- **Given** a head with one in-progress `engine-build-pr-trigger` run that concludes `success` on the
  second lookup
- **When** `make engine-pins-await ENGINE_PINS_AWAIT_SECONDS=2` runs against a fake `gh`
- **Then** it prints `AWAIT <run_id> queued` then `AWAIT <run_id> completed success`
- **And** it exits zero
- **Test:** `tests/test_engine_pins_await.py::test_window_waits_until_the_producer_concludes`

#### Scenario: nothing repinned means nothing to await

- **Given** a change that repins no engine cell
- **When** `make engine-pins-await` runs
- **Then** it prints that no cell was repinned and exits zero without any registry or workflow lookup
- **Test:** `tests/test_engine_pins_await.py::test_no_repinned_engine_skips_the_await`

#### Scenario: the await never dispatches and always lands before the battery

- **Given** the await seam's code and the unit lane's step list
- **When** the seam is inspected and the lane is read
- **Then** the seam issues no `dispatches`, no `reruns`, no `cancel` and no `POST`
- **And** `pipeline.yml`'s `unit` job lists the await step at a lower index than the
  `make ci-unit` step
- **Test:** `tests/test_engine_pins_await.py::test_await_is_read_only_no_dispatch_rerun_or_requeue` and
  `tests/test_engine_pins_await.py::test_the_await_runs_before_the_gate_that_uses_it`
