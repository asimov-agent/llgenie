# Proposal: pr-trigger-cell-detection

## Why

`scripts/engine_build_trigger.py` dispatches one engine-build producer per REPINNED ENGINE,
without an `arch` field. The producer's matrix then applies its default narrowing
(`DEFAULT_CPU_ONLY` engines build only their cpu cell when no arch is named, issue #1836), so a
PR that repins a GPU cell of such an engine never gets that cell built. Measured on PR #2582
(rocm/vllm base-access, issue #2553): the change retagged `llgenie/vllm:3a4d82f5-d04739cb-rocm`,
the trigger's producer run 43248400389 dispatched only `engine-build-vllm-cpu`, and the rocm tag
stayed unpublished — the may-arm gate (`make check-engine-pins-published`, which expands a
repinned ENGINE to all its committed cells, incl. rocm) stayed red until a human dispatched
`engine=vllm arch=rocm push=true` out-of-band (run 43264436280). GitHub issue: #2590.

## What Changes

- `scripts/check_engine_pins_published.py` gains `repinned_cells(base, root)`: the cell view of
  `repinned_engine_ids` — every `(engine, variant)` whose published TAG identity moves between
  `base` and this tree (same `_tag_at` vs `_current_tag` comparison as `retagged_engine_ids`,
  collected per cell instead of deduped to an engine id). A missing base copy or unreadable base
  bytes yield `""` != current tag, so a first import dispatches every one of its enabled cells.
- `scripts/engine_build_trigger.py` switches from per-engine to per-cell dispatch: it dispatches
  `engine-build` with `engine=<id> arch=<variant> push=true` for every repinned cell (a repinned
  cell must never be silently dropped by the arch-less default narrowing; an explicit arch also
  activates the #2561 "build the cell it names or die at the matrix step" semantics). `--engine`
  / `--arch` narrow the cell set as before; report/dry print the cell plan.
- `repinned_engine_ids` (the may-arm) stays semantically identical — its engine verdict is now
  derived from `repinned_cells` plus the params-FILE-diff union, one code path.
- Tests: the existing monkeypatch seam in `tests/test_engine_build_trigger.py` moves to
  `repinned_cells`; a new test proves a repinned GPU cell of a `DEFAULT_CPU_ONLY` engine is
  dispatched with its explicit arch, and a new fixture test in
  `tests/test_check_engine_pins_published.py` proves the cell-level tag diff on a synthetic git
  tree. `tests/test_check_engine_pins_published.py`'s dispatch-forms/BOTS doc surfaces are
  regenerated.

## Non-goals

- The producer matrix's `DEFAULT_CPU_ONLY` default (issue #1836) stays: whole-set sweeps still
  build cpu cells only for such engines. This change names the cell explicitly at dispatch time.
- The liveness sweep (#2579) already dispatches explicitly per cell or as one sweep; untouched.
