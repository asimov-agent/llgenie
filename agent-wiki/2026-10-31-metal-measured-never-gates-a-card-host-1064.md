# Metal-measured figures never gate a card host (issue #1064/V2)

`rank_engines(model, arch)` orders every engine that has a plan for the model, best
first. The `variant` field on a returned row names the image build that figure came
from. Before this change, at a **card arch** (`cuda` / `rocm` / `vulkan`) the variant of
every row was set to the requested arch, so a row whose measurement was taken on
**Metal** was labelled as the card's own build — e.g. MLX (an Apple-native, non-container
engine) surfaced as `{variant: cuda, measured_on: Metal}`. That dressed a Metal-measured
t/s number up as the cuda build's figure, contradicting issue #669's rule that "a Metal
run never gates a cuda/rocm/vulkan/cpu host".

## What changed

One rule in `scripts/model_engine_pick.py`, in the row-building `add()`:

```
if arch in CARD_ARCHES and mb == "Metal" and variant != "cpu":
    variant = "cpu" if "cpu" in info["variants"] else None
```

At a card arch, a Metal-measured row is other-hardware evidence and falls back to the
engine's **cpu** build — the identical pattern already used for a ROCm/CPU figure at a
card host (`llama.cpp (LaurentZuijdwijk fork)` at cuda shows `variant=cpu,
measured_on=ROCm`). The engine is still offered (live resolution for an uncatalogued
model), honestly labelled rank 3; it is never dressed as the requested card's variant.

## Why it is the right guard

- Coherence follows what the engine actually **builds per arch** (its params `variants`),
  not a blanket relabel: only at a card arch, and only when the measurement is Metal, does
  the variant fall back to cpu.
- A Metal-native engine remains offerable at a card host — the fix relabels, it does not
  hide — which keeps live resolution intact for a model the quant catalog has not covered.
- Default `check`/`report` paths are untouched, as are Strata/TensorFold planning.

## Verified against

- Whole-registry `rank_engines(m, "cuda")` over `data/models.json`: no
  `{MLX, variant: cuda, measured_on: Metal}` row anywhere.
- New regression `test_a_metal_measured_figure_never_gates_a_card_host` in
  `tests/test_card_gate_measured_vram.py`.
- Contract restated in `tests/test_model_engine_pick.py` at a cuda host (cpu on Metal
  measurement OR disabled cuda image).
- Full affected surface green: card-gate 10/10, model-engine-pick 15/15,
  registry-sync-trend 10/10, `test_trend_pick` 96/96.
