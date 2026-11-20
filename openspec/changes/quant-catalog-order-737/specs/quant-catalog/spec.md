# quant-catalog spec delta

## ADDED Requirements

### Requirement: The generator emits each cell's plans in a repository-chosen order

`scripts/gen_trending_quant_catalog.py::_model_catalog` SHALL write each `(model, engine)`
cell's plan list in the order the repository chooses — ascending `size_gb`, then `repo`,
then `path` — never in the order a `sort=downloads` Hub search happened to return. The
committed `data/trending-quant-catalog.json` is thereby reproducible from the repository:
two generations over the same Hub answers SHALL be byte-identical regardless of the order
the candidate repos come back in. (A GGUF cell picks ONE repo by the Hub's ranking — that
selection stays Hub-driven; the rule is that the plans a cell lists come out in the
repository's order.)

#### Scenario: shuffled candidates produce the identical cell

Given the Hub candidates for one cell arriving in a different order,
When the generator builds that cell,
Then the cell is identical to the cell generated from the same candidates in any other order.
- **Test:** `tests/test_quant_generator_edges.py::test_a_cell_is_generated_in_repository_order_whatever_order_the_hub_returns`

#### Scenario: two replays of the same answers are byte-identical

Given one recorded set of Hub answers,
When two independent generator passes replay it,
Then both payloads are byte-identical, in the repository's order.
- **Test:** `tests/test_trending_quant_catalog.py::test_two_replays_of_the_recorded_answers_are_byte_identical`

#### Scenario: carry-over does not undo the order

Given a sync that carries a still-reachable plan the live search dropped,
When the carried plan is re-inserted into its cell,
Then the cell is still in the repository order, so the table a sync writes is exactly what a
replay of the same answers reproduces.
- **Test:** `tests/test_quant_catalog_compare.py::test_the_carried_over_plan_lands_in_the_cells_repository_order`

### Requirement: Quant rank is a size decision, never a row order

The picker SHALL rank a cell's quant plans by their stated size (`pick_quant` takes the
largest plan that fits the host's budget through explicit size comparison), so the order of
a catalog row is presentation, never rank. `engine_supported_quants` SHALL return its
budget-fit plans in ascending size independently of the order the committed row lists them.

#### Scenario: the quant range sorts by size whatever the row lists

Given a committed cell that lists its plans in an order other than ascending size,
When `engine_supported_quants` returns the budget-fit plans,
Then they come out sorted by size.
- **Test:** `tests/test_pick_quant_catalog.py::test_the_quant_range_is_sorted_by_size_whatever_order_the_row_lists`

## MODIFIED Requirements

### Requirement: The catalog check fails on a lost plan, and notes what the live Hub re-reads

`make check-quant-catalog` SHALL fail when a row the committed
`data/trending-quant-catalog.json` HAS is no longer produced by
`scripts/gen_trending_quant_catalog.py` — a plan gone, a plan whose repo/files/size/link
changed, an engine's arch list changed, or a table rendered for another registry.

Because the generation is now reproducible (the repository owns the cell order), it SHALL
also fail when the committed cell holds the SAME set of plans the generation produces but
lists them in a different order — the committed table must carry the generation's order, and
the fix is `make sync-quant-catalog`, not a note.

It SHALL NOT fail on what the live Hub re-reads: a plan the search no longer returns but
whose own link still answers, or a conversion upstream has newly published. Both SHALL be
printed as a `[quant-catalog] NOTE:` line and the check SHALL exit 0, because recording
them is the weekly `make sync-quant-catalog`'s job.

#### Scenario: a reorder is now a failure, not a note

Given a committed cell whose plans the reproducible generation emits as the same set in a
different order,
When the check compares the committed table with that generation,
Then the check exits 1 and names the cell whose order is not the generation's.
- **Test:** `tests/test_trending_quant_catalog.py::test_a_reordered_cell_is_a_failure_once_generation_is_reproducible`

#### Scenario: a plan the committed table lost still fails

Given a committed table whose cell records a plan,
When the generator regenerates that cell without it,
Then the check fails, naming the plan it can no longer produce.
- **Test:** `tests/test_trending_quant_catalog.py::test_a_plan_the_committed_table_has_and_the_generator_lost_still_fails`

#### Scenario: a changed plan still fails

Given a committed plan pointing at one file,
When the generator regenerates it pointing at another,
Then the check fails, because the committed table would ship an unverified download.
- **Test:** `tests/test_trending_quant_catalog.py::test_a_changed_plan_still_fails`

#### Scenario: a conversion upstream published is reported, never failed

Given a fresh generation holding a plan the committed table does not record yet,
When the check compares them,
Then the addition is a note and the exit status stays 0.
- **Test:** `tests/test_trending_quant_catalog.py::test_a_repo_upstream_publishes_since_the_sync_is_a_note_not_a_failure`

#### Scenario: a catalog rendered for another registry still fails

Given a committed table rendered for an older `data/models.json`,
When the check regenerates from the current registry,
Then the check fails and says to run `make sync-quant-catalog`.
- **Test:** `tests/test_trending_quant_catalog.py::test_a_catalog_rendered_for_another_registry_still_fails`
