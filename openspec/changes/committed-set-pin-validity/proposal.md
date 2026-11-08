# committed-set-pin-validity — proposal

Issue: [#2190](https://github.com/asimov-agent/llgenie/issues/2190)

## Why

`check_engine_pins_published.py` closed the PR side of the publish-gap: an engine THIS change repins
must have its exact tag resolve a manifest before merge (issue #1622). But a pin that was bumped and
never rebuilt — `tensorfold/cuda` pinned at `ef27f74f` (upstream v1.2.1, bump #1519) whose resolved tag
`llgenie/tensorfold:ef27f74f-ab048303-cuda` returned `manifest unknown` (HTTP 404) from GHCR while the
newest published cuda tag was the OLDER pin `dee65c75` — sat committed and silently broken on `main`,
because no subsequent PR repinned it and the repin-only gate never fires for a pin nobody re-pins. A
fresh install cannot resolve the pinned cuda cell.

## What Changes

- **`scripts/check_engine_pins_published.py`** — adds `committed_cells()` (every committed enabled
  engine cell, all backends, derived from the params matrix) and `check_committed()`, which sweeps the
  FULL committed set and exits 1 when any exact tag resolves no manifest. `check --all` runs it.
- **Makefile** — new `check-engine-pins-valid` target invoking `check --all`; `.PHONY`-declared.
- **`containers/engines/params/tensorfold.json`** — unchanged (fix chosen is **publish**, not repin:
  the pinned `ef27f74fdd…` is the upstream-valid annotated tag object for `refs/tags/v1.2.1`, and the
  missing image is a publish-gap fixed by the engine-build producer, never a local build).
- **tests** — hermetic red (committed tag 404s → rc 1) and green (same committed tag resolves → rc 0)
  sabotage loop; committed-set enumeration covers all nontrivial cells; wiring test for the
  `check-engine-pins-valid` target + `.PHONY`; one `@pytest.mark.network` live sweep of every committed
  cell's exact tag.

This guard makes the recurring class structurally impossible: a committed engine tag that resolves to
`manifest unknown` now fails `check --all` regardless of whether any PR moved the pin.
