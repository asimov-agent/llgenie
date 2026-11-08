# registry-liveness-dispatch

## ADDED Requirements

### Requirement: the liveness gate dispatches the publish for a missing committed tag

`registry-liveness` MUST, whenever its `ALL=1` hard-fail run finds any committed enabled engine tag
misspublishing (HTTP 404 / manifest unknown), dispatch `engine-build` with `push=true` for that
engine×arch — not merely file a tracking issue that stays red. The hard-fail (`exit $rc`) is NOT
weakened: a missing tag still turns the run red, and the dispatch runs in addition.

WHEN `make check-engine-pins-published ALL=1` finds a tag that resolves no manifest
THEN the job exits non-zero AND a subsequent always-step dispatches `engine-build` (via
`gh workflow run engine-build.yml --ref main -f engine=<id> -f arch=<variant> -f push=true`) for that
missing cell, so a partial publish stops being a 5-day-red unrepaired gap and becomes a self-dispatched
build.

#### Scenario: a missing committed tag drives a push=true dispatch

- **Given** the fleet gate names `NOT PUBLISHED ghcr.io/asimov-agent/llgenie/vllm:3a4d82f5-9be509b4-cuda`
- **When** the always-step parses the tag
- **Then** it derives engine=`vllm`, arch=`cuda` and runs `engine-build` with `push=true`
- **Test:** `tests/test_check_engine_pins_published.py::test_the_liveness_workflow_dispatches_the_publish_not_just_names_it`
  asserts the workflow carries the dispatch step, `actions: write`, `-f push=true`, and the
  arch-deriving parser, and that `exit "$rc"` (the ALL=1 hard-fail) is untouched

#### Scenario: all tags published, nothing dispatched

- **Given** every committed enabled cell's tag resolves a manifest
- **When** the fleet gate exits 0
- **Then** the always-step prints "all committed engine tags published; nothing to dispatch" and
  exits 0
- **Test:** the workflow's early-return branch (green fleet) is asserted in the same shape test

### Requirement: the producer sweep collects instead of aborting on the first cell failure

The engine-build sweep for an engine MUST attempt EVERY enabled CI cell, publish the cells that
succeed (when `push`), NAMED the failures on stderr, and exit 0 only when every cell succeeded — so a
params edit that retags every backend cell no longer leaves the later cells at their new hash silently
unpublished when the first cell fails.

WHEN `engine_image.collect(engine, push=False)` is run over an engine whose first cell fails AND whose
later cells succeed
THEN it still attempts the later cells, reports "N ok, M failed" naming the failures, and exits 1;
when every cell succeeds it exits 0, and with `push=True` the successful cells are pushed.

#### Scenario: first cell fails, later cells still attempted and successes built

- **Given** an engine whose cpu cell fails and whose cuda+rocm cells succeed
- **When** `collect` runs over that engine
- **Then** it attempts cpu, cuda AND rocm (does not abort after cpu), reports `2 ok, 1 failed`,
  names `vllm/cpu` on stderr, and exits 1
- **Test:** `tests/test_engine_build_collect.py::test_a_cell_failure_named_and_successes_built`

#### Scenario: a pinned-unchanged install-line change still counts as a repin

- **Given** a params file whose `pinned` is equal on base and head but whose install line differs
- **When** `repinned_engine_ids` compares the params file
- **Then** the engine is still in the repin set (the trigger keys on the whole params FILE, so a
  torch-version edit at an unchanged `pinned` fires the producer)
- **Test:** `tests/test_engine_build_collect.py::test_pinned_unchanged_but_install_changed_still_repins`

### Requirement: the reactor's pins-publish issue names the publish remedy

The issue a `registry-liveness` / pins-publish failure files MUST name the publish remedy (confirm the
dispatch, land `push=true`, keep open until the tag resolves) instead of "no PR this bot can repair
was found", so a reader knows the failure self-heals by dispatching the producer, never by editing
code.

WHEN `run_failure_reactor` files an issue for a run whose workflow is `registry-liveness` or whose log
names a `NOT PUBLISHED` / `manifest unknown`
THEN the issue body names the publish remedy and the acceptance criteria measure the tag's manifest
resolving, not a code change.

#### Scenario: a registry-liveness publish-gap issue names the dispatch

- **Given** a failed `registry-liveness` run whose log names a `NOT PUBLISHED` tag
- **When** `issue_body` builds the issue
- **Then** it includes "Confirm the gate dispatched the publish" and "Move the pin to a published
  commit or dispatch «engine-build» with «push=true»"
- **Test:** `tests/test_run_failure_reactor.py` (29 passed) includes the publish-class body path
