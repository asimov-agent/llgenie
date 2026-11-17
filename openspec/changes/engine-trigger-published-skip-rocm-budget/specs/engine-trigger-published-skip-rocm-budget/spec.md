# engine-trigger-published-skip-rocm-budget

## ADDED Requirements

### Requirement: a cell whose exact tag is already published is skipped, not re-dispatched

Before dispatching a producer, `engine_build_trigger.py` MUST probe the registry for the cell's exact
committed tag (the `<pin8>-<hash8>-<variant>` tag the may-arm #1622 computes, probed with the same
`_digest_http` manifest lookup). A cell whose tag resolves a manifest is concluded `PUBLISHED-SKIP`
with NO producer dispatch; only a cell whose tag is absent is dispatched. Reopen/sync cycles then cost
seconds for already-published cells instead of re-firing a full matrix re-shuffle.

WHEN a repinned cell's exact committed tag already resolves a registry manifest
THEN the trigger concludes that cell `PUBLISHED-SKIP` and dispatches no producer for it

#### Scenario: all cells published dispatches zero producers and exits 0

- **Given** a PR that repins one cell whose exact committed tag resolves a registry manifest
- **When** the trigger runs check against that cell
- **Then** it dispatches ZERO producers, prints `PUBLISHED-SKIP`, and exits 0
- **Test:** `tests/test_engine_build_trigger.py::test_every_cell_published_dispatches_zero_and_exits_zero`

#### Scenario: an unnameable tag is never a published-skip decision

- **Given** a cell whose tag identity cannot be computed (an engine-shaped fixture, an unreadable input)
- **When** the trigger probes it
- **Then** it treats the cell as not published and dispatches it (no probe decides on a tag it cannot name)
- **Test:** `tests/test_engine_build_trigger.py` (the `surogate` fixtures — a variant-not-present cell
  dispatches; covered by `test_a_404_poll_that_is_visible_in_the_run_list_concludes_success`)

### Requirement: per-arch-class wait budgets, with --wait-min overriding every class

The wait budget a cell is awaited with MUST come from its arch class, not a flat 60: a cold ROCm cell
is awaited with `150` minutes against the `60`-minute default for `cpu`/`cuda`/`vulkan`. An explicit
`--wait-min` must override every class. The clock the build is judged against therefore reflects when a
cold/queued ROCm cell can actually run, while every other class keeps the flat bound.

WHEN the trigger awaits a producer for a cell
THEN its budget is the class budget (`rocm`=150, `cpu`/`cuda`/`vulkan`=60) unless `--wait-min` is given, which overrides every class

#### Scenario: rocm is awaited with its cold-build bound, the rest keep the flat 60

- **Given** a cell with variant arch `rocm`, `cpu`, `cuda` or `vulkan`
- **When** no explicit `--wait-min` is passed
- **Then** `rocm` resolves to 150 minutes and `cpu`/`cuda`/`vulkan` resolve to 60
- **Test:** `tests/test_engine_build_trigger.py::test_per_arch_wait_budgets_rocm_gets_150_cpu_cuda_vulkan_keep_60`

#### Scenario: an explicit --wait-min overrides the class budget

- **Given** an explicit `--wait-min 60` on a `rocm` cell (or `--wait-min 120` on a `cpu` cell)
- **When** the per-cell budget is resolved
- **Then** the explicit value wins over the class default
- **Test:** `tests/test_engine_build_trigger.py::test_per_arch_wait_budgets_rocm_gets_150_cpu_cuda_vulkan_keep_60`

### Requirement: a cancelled producer is replaced at most once per (cell, trigger run)

When a dispatched producer concludes `cancelled` (a cancellation storm), the trigger MUST dispatch at
most ONE replacement for that cell — never a second — and the replacement MUST inherit the cell's
REMAINING wait budget, so repeated cancellations cannot re-queue the same cell unboundedly or spend
more than its per-class bound. If the replacement is also cancelled, the cell fails (it is not looped).

WHEN a dispatched producer for a cell concludes cancelled
THEN the trigger fires at most ONE replacement dispatch for that cell, within the remaining budget; a second cancellation fails the cell

#### Scenario: a cancelled producer with budget left gets one replacement

- **Given** a queued producer that concludes `cancelled` while the cell still has budget
- **When** the trigger's cell logic awaits it
- **Then** it dispatches exactly one replacement within the remaining budget and records `replaced`
- **Test:** `tests/test_engine_build_trigger.py::test_a_cancelled_producer_yields_at_most_one_replacement_dispatch_per_cell`

#### Scenario: the replacement budget is capped by what remains

- **Given** a cell whose whole wait budget is already consumed by the (cancelled) first producer
- **When** `_await_cell` runs
- **Then** no replacement is dispatched and the per-cell cap is recorded (`replace_cap`)
- **Test:** `tests/test_engine_build_trigger.py::test_await_cell_withholds_replacement_when_the_budget_is_already_spent`
