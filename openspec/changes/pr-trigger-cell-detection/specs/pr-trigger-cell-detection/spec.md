## ADDED Requirements

### Requirement: a repinned cell is detected at cell granularity
The repository SHALL expose `repinned_cells(base)` in `scripts/check_engine_pins_published.py`:
the list of `(engine, variant)` cells whose published tag identity moves between `base` and the
working tree. A cell whose params file or tag inputs cannot be read at `base` counts as moved.
Disabled cells never move. `repinned_engine_ids` SHALL remain the engine-level view (deduped
`repinned_cells` UNION the params-FILE diff), so the may-arm verdict never loosens.

#### Scenario: a GPU cell of a default-cpu-only engine moves
- **WHEN** a change retags `vllm`'s rocm cell (Dockerfile.rocm + params bump) and leaves the cpu
  cell's tag identical
- **THEN** `repinned_cells` names `(vllm, rocm)` and not `(vllm, cpu)`

#### Scenario: a first import moves every enabled cell
- **WHEN** an engine's params file does not exist at `base`
- **THEN** `repinned_cells` names every enabled committed cell of that engine

### Requirement: the pin-bump trigger dispatches every repinned cell explicitly
`scripts/engine_build_trigger.py` SHALL dispatch `engine-build` with `engine=<id>
arch=<variant> push=true` for each cell named by `repinned_cells(base)` (narrowed by
`--engine`/`--arch`), never an arch-less per-engine dispatch. The verdict discipline (the
dispatched run's own conclusion, guard refusals named) is unchanged.

#### Scenario: the #2582 class — a repinned rocm cell gets its producer run
- **WHEN** the change repins only `vllm`'s rocm cell and the trigger runs with `--dry`
- **THEN** the plan lists `engine=vllm arch=rocm` and no arch-less `engine=vllm` dispatch

#### Scenario: no repin stays hermetic
- **WHEN** no cell's tag identity moves and no params file differs
- **THEN** nothing is dispatched and no API is touched
