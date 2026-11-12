# Registry-liveness dispatch reads all four `[select]` fields (issue #2567)

## What changed

The `registry-liveness` dispatch loop parsed its own `[select]` contract lines with
a 3-variable `while read -r engine variant tag`. The gate emits **4** fields per missing
cell, `[select] <engine> <variant> <tag-suffix>` (`scripts/check_engine_pins_published.py:128`),
so every field shifted one slot right: `$engine` became the literal `[select]`, `$variant`
the engine id, `$tag` the "<variant> <tag-suffix>". Measured on the run for `e6b9b4b4f`
(job 131076815722): all 22 dispatch lines read
`dispatching engine-build push=true for [select]/llama.cpp (missing tag cpu 7d7f0287-1b5db7a2-cpu)`
— i.e. the dispatched inputs were `engine="[select]"`, `arch="llama.cpp"`.

`engine-build` matched no committed params id for `engine="[select]"`, synthesized its
`none/none` placeholder, and the runs completed "success" having built and published
nothing — the exact failure mode #2561 documented for nine runs on `aa700cf27`. The
measured backlog (19 committed cells unpublished, stable across 3 consecutive gate
passes) never drained, so every unit gate stayed red.

The fix binds the marker in its own first field — `while read -r sel engine variant tag`
— and skips loudly (never dispatches) any line whose first field is not exactly
`[select]` or which lacks the four cell fields. The committed engine id (dots intact),
the variant and the tag suffix now reach `engine-build` un-shifted. The next
`registry-liveness` run re-dispatches every still-missing cell once with correct inputs.

## Verification

- Hermetic: `tests/test_check_engine_pins_published.py::test_the_liveness_dispatch_reads_all_four_select_fields`
  reads both the gate's `[select]` format string and the workflow's read loop and asserts
  they agree on a 4-field shape with a distinct marker field — falsified against the
  3-variable pre-fix loop (fails `must be a 4-field read`), passes on the fixed loop.
- Guard text (loud `not dispatching` refusal) asserted in the same test.
- `make check-workflows`, `make check-docs`, `make lint` green; the full `make test-unit`
  suite runs the pinned consumers.
- **Environmental note:** this container cannot run or pull the `llgenie/test` and
  `llgenie/openspec` docker images (no `unshare`/overlay capability — `docker build` and
  even `docker pull` fail registering layers), so `make test-unit`, `make loop` and the
  Dockerized `make openspec-validate` could not be executed. Those gates were instead run
  on the host python directly (`scripts/unit_tests.py run`, `scripts/lint_linefeeds.py`)
  and the openspec CLI was installed via npm (the Darwin fallback path) and driven
  directly. The one live `@pytest.mark.network` test
  (`test_every_committed_engine_cell_tag_is_published_live`) is excluded from the hermetic
  gate by marker and fails only because 19 committed cells genuinely resolve no manifest
  — the exact backlog this issue names, confirmed live.

## Current status

This is the change for issue #2567. The deferred "engine-build should red, not vacuously
succeed, for an unknown `inputs.engine`" guard is filed as #2568 (referenced from #2567's
`Not covered`, and #2568 links back here). Not merged; the change leaves the tree for the
job to commit and open the PR.
