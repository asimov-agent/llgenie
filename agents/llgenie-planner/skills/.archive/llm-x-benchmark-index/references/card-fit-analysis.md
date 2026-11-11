# Card-fit / VRAM analysis — deriving "what fits my card" from the store

## Probe the live store with the project's own classifiers

Store shape drifts and memory is stale. Build an evidence table with the real
logic, not by trusting the JSON:

```python
import json, sys; sys.path.insert(0, 'scripts')
import update_trending as ut
store = json.load(open('data/models.json'))
for m in store['models']:
    for e in m.get('engines', []):
        total = ut.hardware_vram_gb(e.get('hardware') or '')  # card size from free text
        scope = ut.in_scope(e)          # passes the ≤48GB consumer/workstation gate?
        b = ut.measurement_backend(e, store['engines'])  # CUDA/ROCm/CPU/Metal table
        core = ut._tps_core(e.get('tps'))  # numeric core of an estimated range
```

Count models vs measurements; count how many hardware strings parse (the rest
are Apple/platform/bare part names); find measurements that read datacenter-ish
but `in_scope()` still accepts — that is scope-gate drift, not a data quirk.

## Per-measurement vs model-level dimensions, and contract pruning

- Model-level OPTIONAL keys exist (`weight_gb`, `system_ram_min`,
  `context_tokens`, `storage_offload`) but cover only some models and CANNOT
distinguish two quants of the same model; only model-level `vram_min` /
`vram_tier` are required.
- The measurement items (`model_contract.json` → models[].engines[].items) set
  `additionalProperties: false`, so a new per-measurement key the crawl writes
  is pruned SILENTLY at ingest. Adding one requires all three, in one change:
  (1) widen the contract with the OPTIONAL key (additive-only — never
  `required`, never edit an already-generated snapshot); (2) a
  `normalize_model` + test change proving the key survives ingest; (3) a
  crawl-ask change (`Makefile:101 DIM_ASK` + the gather-data skill) so the agent
  records it per measurement. A field nobody asks for stays empty.
- Check what the crawl actually captures before proposing a field:
  `grep DIM_ASK Makefile` + the gather-data skill rules.

## Honest footprint precedence for a "fits" claim

A model belongs in tier T only when a measurement's footprint fits T. Sources in
precedence, each labelled:
1. per-measurement footprint the POST states → `stated` (needs N GB);
2. model-level `weight_gb` when it matches the measurement's quant →
   `model-level`;
3. the card the figure was measured on (`hardware_vram_gb(hardware)`) →
   `measured-on`: an UPPER bound — render "measured on N GB", never "needs N";
4. none → `unknown`: list in an explicit "unplaced" note, never drop, never
   guess (a fabricated footprint is a hard no-go).

## Scope gate drift

`MAX_SCOPE_VRAM_GB = 48`; `_DATACENTER_HW` is a hand-maintained token tuple. It
drifts: a datacenter part missing from it passes `in_scope()` because
`hardware_vram_gb()` returns None for a bare part name and only the tuple
excludes it — that figure then earns the speed bonus and can top a card-owned
"best" cell. Grep the tuple for every new datacenter part before trusting a
gated number. The displayed best cell uses unscoped `best_measurement()`; the
speed bonus uses `best_in_scope()` — gate displayed best cells with
`in_scope()`.

## `vram_tier` is a free string

No enum in the contract; stored values drift (`48`, `8`, `CPU`, `16GB`,
`512GB`). Group/order by a DERIVED canonical tier at render, never by the raw
string, and never rewrite stored tiers (the store is additive-only).

## Markdown cannot filter — README vs a Pages page

GitHub README markdown has no script and sanitizes HTML: no dropdown, no
sortable table. An honest markdown filter = anchor-indexed tier tables + a
`<details>` collapse. A real JS dropdown = a generated GitHub Pages HTML page,
which is a new artifact + make target + publish job + ARCHITECTURE row — a
separate tracked phase, not merged into the README-only change.

## Filing the analysis as an issue

Deliverable is a detailed issue: Why → what the store/crawl actually supports
today (measured numbers) → options considered with a verdict → recommended
design (the ONE shared function, the tier tables, the honesty labels) →
acceptance criteria → not-covered. Because this repo's rulebook (AGENTS.md) says
an issue that changes its behaviour must say so, post ONE comment immediately
after creating the issue naming the exact sections that change and marking the
AGENTS.md diff review-required; the code/data/tests half can be reviewed
normally.
