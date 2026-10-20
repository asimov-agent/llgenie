# llgenie reads the registry's stated footprint, not just the VRAM label

## Why

`data/models.json` (a verbatim copy of trending-local-llms') changed shape on 2026-10-20. The model
contract now states **what a run needs** — and llgenie budgets from `vram_tier` plus a Hugging Face
file-size guess only (issue #414).

Measured against upstream `master` (`generated_utc=2026-10-19T19:24:53Z`) vs the vendored copy
(`2026-10-13T14:31:40Z`):

```
vendored  models=23  engines=24  generated_utc=2026-10-13T14:31:40Z
upstream  models=50  engines=30  generated_utc=2026-10-19T19:24:53Z
```

New, additive, optional — on the **model** *and* inside an individual `engines[]` measurement
("the footprint of that run", `data/MODEL_CONTRACT.md`):

| field | meaning |
|---|---|
| `weight_gb` | weight footprint per format + quant (`5.95GB Q4_K_M`) — the budget before any context |
| `context_tokens` | the window the KV cache is sized for (`131072`, `128K`, `1M`) |
| `system_ram_min` | system RAM / unified-memory requirement, when a post states it |
| `storage_offload` | storage-offload requirement (`640GB NVMe, experts on SSD`) |
| `engine_min_version` | required engine build / flags (`llama.cpp b6xxx, --n-gpu-layers 99`) |

Two consequences today: a model whose `system_ram_min` exceeds this host's RAM is offered anyway
(the VRAM column fits), and a model whose stated weights exceed the budget is reported as "smallest
GGUF is N GB" — an estimate of a *file* — rather than by the measured run.

The **data** sync itself is blocked upstream, and the branch must not paper over it: the new snapshot
is lossy (24 losses: 18 `(engine, hardware)` measurement groups, 6 lowered t/s / engagement figures),
so `make check-registry-keys` refuses it. Reported as andyholst/trending-local-llms#463; the weekly
`registry-sync.yml` job lands the store once it is additive again.

## What Changes

- **`scripts/model_engine_pick.py`** — `FOOTPRINT_FIELDS`, `stated_gb()` (`5.95GB` → 5.95, `800MB` →
  0.78, `640GB NVMe…` → 640), `stated_context()` (`128K` → 131072, `1M` → 1048576), `footprint(model,
  measurement)` (the measurement's own value wins; only stated fields appear) and
  `stated_budget_gb()`. `fits()` gains an optional `ram_gb` and refuses a model whose stated
  `system_ram_min` exceeds it; `trend_list()`/`recommend()`/`offer()` thread that RAM through;
  `rank_engines()` puts the run's footprint on each engine row; `_no_fit_reason()` cites the stated
  RAM floor and stated weights before any download guess, and mentions `storage_offload`.
- **`scripts/registry_keys.py`** — `GROW_ONLY_SCALARS = (weight_gb, context_tokens, system_ram_min)`:
  a lowered model-level value and a measurement's lost/lowered own footprint are findings, the way a
  lowered t/s is. A restated value (`5.95GB` → `5.95 GB`) is not a loss, and absent stays absent.
- **`tests/test_registry_footprint.py` (new, 12 cases)** — the parsing, the measurement-wins rule, the
  RAM floor in `fits`/`trend_list`, the engine row's footprint, the reason text, and the four guard
  behaviours. Nothing is mocked: the real picker and the real guard run.
- **README + `agent-wiki/`** — the new fields, what llgenie does with each, and that the data sync is
  waiting on the upstream store.

## Impact

- Affected specs: `registry-contract` (new capability).
- Affected code: `scripts/model_engine_pick.py`, `scripts/registry_keys.py`,
  `tests/test_registry_footprint.py` (new), `README.md`, `agent-wiki/`.
- No behaviour change for a store that states no footprint (today's vendored copy): every new value is
  optional and absent means "decide as before".
- No data change in this PR: `data/models.json` stays at the 2026-10-13 snapshot until upstream's store
  is additive again (`ci-unit` would red on the lossy copy).

## Not covered (each its own issue)

- andyholst/trending-local-llms#463 — the 2026-10-19 snapshot is lossy (24 losses); llgenie's guard
  refuses it by design, and never patches upstream data to make a sync pass.
- The data sync + its derived artifacts remain the weekly `registry-sync.yml` job's output.
- Surfacing `context_tokens` in the launcher's `-c` choice (the local-file path in
  `scripts/llgenie_serve.py`) is a separate change: it tunes from the GGUF header, not the registry.
