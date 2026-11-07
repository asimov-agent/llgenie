# vram-range-scope-view

## ADDED Requirements

### Requirement: a single scope filter turns the full registry into the view for a VRAM range

A pure function `scope_models(registry, vram_range=DEFAULT_VRAM_RANGE)` MUST
return a NEW registry (never the input's `models` identity, never a mutation
of the input) containing exactly the models whose VRAM requirement falls
within `[lo, hi]`, where `DEFAULT_VRAM_RANGE = (8.0, 48.0)` GB (the
consumer/workstation band). A model's VRAM requirement is its stated
`vram_min` when it parses to a number, else its `vram_tier` when that parses
to a number; a model with neither (a CPU/Apple-only row, or a tier that is
non-numeric) is always in scope (it has no VRAM requirement to band against).

WHEN `scope_models` is given the full vendored registry and the default range,
THEN it returns exactly the in-band models as a fresh dict.
WHEN a model's requirement is below `lo` or above `hi`, THEN it is absent from
the returned `models` but present in the input (it is filtered, not dropped).

#### Scenario: default band includes 8–48 GB and excludes out-of-band tiers

- **Given** the full vendored `data/models.json` with `cyber-frost-3.8-mlx`
  (128 GB) and `deepseek-r1-1.5b` (2 GB) present
- **When** `scope_models(registry)` runs (default range 8–48 GB)
- **Then** a mid-band model is present, and `cyber-frost-3.8-mlx` and
  `deepseek-r1-1.5b` are absent from the returned `models`
- **And** both are still present in the input registry (not dropped)
- **Test:** `tests/test_vram_scope_filter.py::test_scope_default_excludes_out_of_band_and_keeps_the_file_intact`

#### Scenario: a wide range includes the 128 GB entry again

- **Given** the default filter omitted a 128 GB model
- **When** `scope_models(registry, (8, 512))` runs
- **Then** the 128 GB model is back in the returned `models`
- **Test:** `tests/test_vram_scope_filter.py::test_scope_wide_range_includes_the_out_of_band_entry`

### Requirement: every consumer reads the scoped view

`trend_list`, `recommend`, `offer`, `matrix`, and `rank_models` MUST accept a
`vram_range` parameter (default `DEFAULT_VRAM_RANGE`) and MUST apply
`scope_models` to the registry before doing their work, so the pick, the offer
list and the per-`(arch, ram, vram)` matrix all read the filtered view rather
than ad-hoc per-call checks.

WHEN any of these consumers runs with the default range,
THEN its rows are a subset of `scope_models(registry, DEFAULT_VRAM_RANGE)`.
WHEN a consumer runs with a wider `vram_range`,
THEN out-of-band entries enter its rows again.

#### Scenario: matrix rows are scoped to the default band by default

- **Given** the full registry and a consumer
- **When** `matrix(registry, vram, ram, arch)` runs
- **Then** every permutation/skipped model id is in the default-scope set
- **And** a 128 GB model is absent unless `vram_range` includes its tier
- **Test:** `tests/test_vram_scope_filter.py::test_consumers_read_the_scoped_view`

### Requirement: a committed default-range view is make-regenerated and CI-checked

A committed view `tests/fixtures/vram-scope-view.json` MUST list the
default-range scoped model ids with the registry `generated_utc`, the range
and its provenance note. `make render-vram-scope-view` MUST rewrite it from the
live vendored registry and `make check-vram-scope-view` MUST fail when the
committed file differs from what the renderer computes — so a change to the
filter or to the range shows up as a reviewable diff.

WHEN the filter or the committed registry changes,
THEN the committed view must be re-rendered and CI validates the diff.

#### Scenario: a stale committed view reds the gate

- **Given** a committed `vram-scope-view.json` from an older registry/filter
- **When** `make check-vram-scope-view` runs
- **Then** it fails naming the stale file and the render command
- **Test:** `tests/test_vram_scope_filter.py::check_vram_scope_view_gate`
  (gate-level; the `ci-unit` round runs `make check-vram-scope-view`)
