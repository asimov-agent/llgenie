# trigger-wait-budget-2892

## ADDED Requirements

### Requirement: a repinned cell whose exact tag already resolves a registry manifest is published-skip, never re-dispatched

Before dispatching a producer for a repinned cell, `check` MUST probe the cell's EXACT tag
(`check_engine_pins_published.exact_tags` -> `engine_image._digest_http`, the same publish authority as
the merged may-arm) in the registry. A cell whose tag resolves a manifest MUST be printed as a
published-skip naming the tag, MUST NOT be dispatched, and MUST NOT count as a failure. A pass whose
every repinned cell is published-skip MUST exit 0 with zero dispatches. `report` and `check --dry`
MUST NOT touch the network.

WHEN a repinned cell's exact content tag already resolves a registry manifest
THEN the trigger prints `published-skip`, dispatches nothing for that cell, and exits 0 when every cell skipped.

#### Scenario: every cell published — zero dispatches, exit 0

- **Given** a repinned cell whose exact tag resolves a manifest (fake digest probe returns a digest)
- **When** the trigger runs `check`
- **Then** it dispatches NOTHING (zero `gh workflow run` calls recorded), prints `published-skip` naming the tag, and exits 0
- **Test:** `tests/test_engine_build_trigger.py::test_a_published_cell_is_skipped_and_never_dispatched`
  stubs the repin set and the digest probe, asserts the recorded dispatch argv list is empty and `rc == 0`

#### Scenario: an unpublished cell still dispatches and awaits as today

- **Given** a repinned cell whose tag resolves NO manifest (fake digest probe returns `("", reason)`)
- **When** the trigger runs `check`
- **Then** the cell is dispatched with its explicit arch and its verdict awaited exactly as today, and the published-skip line is absent
- **Test:** `tests/test_engine_build_trigger.py::test_an_unpublished_cell_still_dispatches_and_awaits`
  (existing dispatch/await assertions under the new probe) assert one dispatch and `rc == 0` on a success verdict

### Requirement: the wait bound is per-arch — rocm gets a budget above its measured cold-build bound

The per-producer wait bound MUST come from `WAIT_MIN_BY_ARCH` (`{"rocm": 150}`) falling back to
`DEFAULT_MAX_WAIT` (60) for every other arch. An explicit `--wait-min` MUST override every class
exactly as today. An expired wait MUST name the ACTUAL bound that expired for that cell's arch.

WHEN a rocm cell is awaited without an explicit `--wait-min`
THEN its producer is awaited up to 150 minutes, not 60, and the expiry line names `150 min`.

#### Scenario: a rocm cell gets 150, a cpu cell keeps 60

- **Given** repinned cells `x/rocm` and `y/cpu` with no `--wait-min`
- **When** the trigger dispatches them
- **Then** the rocm cell is awaited with budget 150 and the cpu cell with 60
- **Test:** `tests/test_engine_build_trigger.py::test_rocm_cell_gets_the_extended_budget_and_cpu_keeps_the_default`
  records the `wait_min` handed to the await step for each cell

#### Scenario: --wait-min overrides every class

- **Given** a rocm cell and `--wait-min 90`
- **When** the trigger dispatches it
- **Then** it is awaited with budget 90
- **Test:** `tests/test_engine_build_trigger.py::test_wait_min_override_applies_to_every_arch`

### Requirement: a cancelled producer gets at most one replacement dispatch carrying the cell's remaining budget

When a dispatched producer ends `cancelled`/`skipped`, `check` MUST re-dispatch that cell exactly once
per trigger run, awaiting it with the CARRIED budget: `budget * REPLACEMENT_FACTOR`
(`REPLACEMENT_FACTOR = 2`) minus the seconds the cancelled attempt consumed (floored at 10 min). When
the replacement dispatch ALSO fails, the FAIL line MUST name that the single permitted replacement
failed, and no further dispatch for that cell may happen in this run. A `guard_refused` producer MUST
NOT be replaced (a refused dispatch is a policy refusal, not a queue casualty).

WHEN a producer is cancelled mid-wait
THEN the cell gets exactly one replacement dispatch whose budget is the cell's total bound minus what the first attempt consumed

#### Scenario: cancelled producer — one replacement, then stop

- **Given** a dispatch whose first producer run ends `cancelled` and whose replacement also ends `cancelled`
- **When** the trigger runs `check`
- **Then** exactly 2 dispatch-await attempts happened for that cell (first + one replacement), the FAIL line names the replacement, and `rc == 1`
- **Test:** `tests/test_engine_build_trigger.py::test_a_cancelled_producer_gets_exactly_one_replacement_then_stops`
  stubs the await step to record every call

#### Scenario: the replacement budget carries what the cancelled attempt consumed

- **Given** a rocm cell (budget 150) whose cancelled attempt consumed 30 minutes of a 300-min total bound
- **When** the replacement dispatch is awaited
- **Then** it is awaited with budget 270 min (300 - 30), not a fresh 150
- **Test:** `tests/test_engine_build_trigger.py::test_the_replacement_carries_the_consumed_budget`
  controls the clock via a stubbed `time.time` and asserts the second await's budget
