# Engine / arch coherence in registry ranking

When a defect in `scripts/model_engine_pick.py` (or a sibling ranking helper) is about a row
that pairs the WRONG `variant` with a `measured_on` figure (e.g. `{engine: MLX, variant: cuda,
measured_on: Metal}`), the fix is NOT whatever first seems tidy. Two wrong fixes and the right
one, learned the hard way:

## Ground coherence in what the engine actually BUILDS per arch — not inference

An engine's row for a host arch must reflect the docker image the engine genuinely builds and
supports for that arch (`engine_params`' `variants`/`native`, or the skill's declared backends).
MLX, for example, declares cuda+cpu+metal builds even though it is Metal-native. So "MLX at a
cuda host" is not automatically incoherent — the incoherence is the *measured_on* the figure
carries, not the engine's presence. Do not reason from "native backend" alone; read the build
capability.

When the user says "what arch types each engine supports / the base image each is built on for
the arch it supports", they mean exactly this: validate against declared build support, not a
rule you invented.

## The correct contract is the CPU FALLBACK, matching existing cross-backend handling

At a **card host** (`cuda` / `rocm` / `vulkan`), a figure measured on a backend that cannot gate
that host (Metal on a card host — Metal is Apple-native and cannot run in a Linux container)
must **fall back to the engine's CPU build**: `variant = "cpu"` when `"cpu" in variants`, keeping
`measured_on` honest (`Metal`). The engine stays offered (so live resolution for an uncatalogued
model still lists it), rank-3 as other-hardware evidence, honestly labelled.

This is exactly how an existing ROCm/CPU figure already lands at a cuda host — so the fix is
consistency with the codebase's existing pattern, not a new rule.

Two variants of the WRONG fix, both of which I shipped and had to revert:
- **Blanket "Metal → metal variant".** Breaks `test_trend_pick`: a servable row at a card host
  must have `variant ∈ (backend, "cpu")`; `"metal"` is never servable on a card host. Also
  shifts pinned top rows (`pinned[("cpu",16)]["id"] == "mlx"`).
- **Exclude the Metal row at a card host.** Breaks `test_model_engine_pick`
  (`test_a_model_the_catalog_does_not_cover_keeps_its_engines` expects MLX present for an
  uncatalogued model) — exclusion silently drops a legitimately-offerable engine.

The CPU fallback satisfies all three simultaneously: `variant ∈ (backend, "cpu")` (passes
`test_trend_pick`), engine still present (passes `test_model_engine_pick`), and no
`{MLX, cuda, Metal}` row (the issue's acceptance line).

## It touches a SHARED helper — run every module that pins its output

`rank_engines` is asserted by several suites at once: `test_card_gate_measured_vram.py`,
`test_model_engine_pick.py`, `test_registry_sync_trend.py`, `test_trend_pick.py`. A narrow run
(e.g. card-gate + model-engine-pick) passed while `test_trend_pick` regressed — a different
module pinning the same helper. Before committing a change to a shared ranking helper, run
every file that imports/pins it. These are slow (~40–70 s per docker run each); run them
per-file in a background process writing to a results file (see the SKILL's test-unit bullet
about the 300 s cell cap), never one foreground cell.

## Regression tests for this class

Add the acceptance assertion to the module that owns the principle (`test_card_gate_measured_vram.py`
for the "a Metal run never gates a card host" rule), and update — don't append a duplicate — any
existing assertion (`test_model_engine_pick:42`) that pinned the old wrong contract, so the two
directions stay complementary and one test does not continue demanding the defect.
