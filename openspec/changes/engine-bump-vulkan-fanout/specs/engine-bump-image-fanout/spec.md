## ADDED Requirements

### Requirement: The bump fan-out dispatches every repinned cell before awaiting a verdict

The engine-bump trigger SHALL dispatch a `push=true` `engine-build` producer for EVERY repinned cell it
intends to prove before it awaits ANY cell's verdict, because every `push=true` run joins one global
`engine-build-push` FIFO and a serial await loop makes each cell's wall time the sum of the cells
dispatched before it.

#### Scenario: A multi-variant wave dispatches all of its cells up front

- **WHEN** a change repins the cpu, cuda, rocm and vulkan cells of one engine
- **THEN** the trigger dispatches four `engine=… arch=…` producers before any producer verdict is awaited
- **AND** each dispatch names its arch explicitly (`#2590`) and never dispatches an arch-less cell

#### Scenario: A published-skip cell is probed but never dispatched

- **WHEN** a repinned cell's exact tag already resolves a registry manifest
- **THEN** that cell is announced as published-skip and is NOT dispatched
- **AND** the remaining cells still fan out before any verdict is awaited

### Requirement: Dispatch order follows the wait budget, ascending

The trigger SHALL dispatch cells in ascending per-arch wait budget, so the cell with the longest measured
build cannot stand in front of a variant the matrix also requires; reporting order stays alphabetical.

#### Scenario: The longest cell is dispatched last

- **WHEN** one engine repins cpu, cuda, rocm and vulkan
- **THEN** the dispatch order is the three default-budget cells followed by the rocm cell
- **AND** the tail variant is never queued behind the longest cell of its own wave

### Requirement: A fan-out cell's wait bound is queue-aware and stays inside the trigger job window

When more than one cell dispatches, the trigger SHALL bound each cell's wait by
`min(FANOUT_MAX_MINUTES, max(cell budget, sum of the wave budgets))`, where `FANOUT_MAX_MINUTES` is below
the dispatched trigger job's own timeout, so the script ends the wait and names the stall instead of the
job being cancelled mid-await. A single dispatching cell SHALL keep its class bound, and an explicit
`--wait-min` SHALL keep that exact bound for every cell.

#### Scenario: A wave widens the bound to its own queue

- **WHEN** four cells dispatch with budgets 60, 60, 150 and 60
- **THEN** each cell is awaited on a bound of `FANOUT_MAX_MINUTES` minutes, not its class budget
- **AND** the bound stays below the trigger job's timeout so the verdict is reported, not truncated

#### Scenario: An explicit override is not widened

- **WHEN** the caller passes `--wait-min`
- **THEN** every cell is awaited on exactly that bound

### Requirement: A dispatched variant that does not end success is named as a missing variant

The trigger SHALL report every dispatched cell that does not end a `success` verdict — expired, stalled
behind the push-group holder, refused at dispatch or at its own guard, or ended `cancelled` / `skipped` /
`failure` — as a missing variant, naming the engine, the variant, the reason, the readable workflow run id
where one exists, and that the bump PR body must carry the gap as `## Not covered` rather than a tick it
cannot back.

#### Scenario: A tail variant expires behind the queue

- **WHEN** a dispatched cell's producer never concludes before the fan-out bound
- **THEN** the failure names the cell, the expired bound, the producer run id and its last status
- **AND** when a `push` run holds the global group, the holder run id is named
- **AND** a `MISSING VARIANT` line names the variant and its owning issue lane

#### Scenario: A poll-visibility race is not reported as a build result

- **WHEN** a producer run id never resolves on either endpoint for the whole bound
- **THEN** the failure names it a poll race to be re-read, not a failed build

### Requirement: The terminal verdict rules survive the dispatch/await split

Awaiting shall keep every terminal rule of the fused dispatch: a cancelled or skipped producer is
terminal and gets at most ONE replacement dispatch on the carried budget, a `success` conclusion is
terminal even when the run's status never reports `completed`, a `404` from either endpoint is re-resolved
from the run list, and only a genuine wall-clock expiry ends the wait.

#### Scenario: A cancelled producer gets one replacement on the carried budget

- **WHEN** a dispatched producer ends `cancelled`
- **THEN** the trigger dispatches at most one replacement awaited on `budget × REPLACEMENT_FACTOR` minus
  the minutes the cancelled attempt consumed, never below `REPLACEMENT_MIN_WAIT`
- **AND** a replacement that also fails is named and ends the cell's dispatches

#### Scenario: A guard refusal is never replaced

- **WHEN** a producer fails at its own trigger guard
- **THEN** the outcome is reported as refused and no replacement dispatch happens
