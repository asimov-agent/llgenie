# The registry states a footprint, and llgenie reads it

Issue #414. OpenSpec change: `registry-contract-sync`. PR: (this branch, opened against `asimov-agent/llgenie:main`).

## What changed upstream (measured 2026-10-20)

`trending-local-llms` shipped a new store and a machine-checkable contract (`data/MODEL_CONTRACT.md`
+ `data/model_contract.json`):

```
vendored (main)  models=23  engines=24  generated_utc=2026-10-13T14:31:40Z
upstream (master) models=50 engines=30  generated_utc=2026-10-19T19:24:53Z
```

New optional fields — on the model **and** inside an `engines[]` measurement ("the footprint of that
run"): `weight_gb`, `context_tokens`, `system_ram_min`, `storage_offload`, `engine_min_version`. Six new
engines (`Janas`, `Magnitude`, `TokenSpeed`, `strixite`, `llama.cpp (hikicoder fork)`,
`llama.cpp (strix-llama.cpp fork)`), 27 new models. The top-level `engines` object shape is unchanged.

## The data sync is blocked upstream — deliberately

`make sync-registry` succeeded (23 → 50 models) but `make check-registry-keys` refused the result with
**24 losses**, all real:

```
qwen3.8-27b: measurement llama.cpp on RTX 4060 8GB is gone (1 measured row(s) before)
qwen3.8-27b: mlx-serve on M4 Max t/s lowered 146 -> 70
qwen3.8-27b: mlx-serve on M4 Max views lowered 4903 -> 755
bonsai-2-27b: llama.cpp (PrismML fork) on RTX 3060 12GB likes lowered 16769 -> 16739
qwen3.8-flash-next-125b: measurement Strata on RTX 3090 is gone (1 measured row(s) before)
llama-3.1-8b: measurement vLLM on RX 7900 XTX is gone (1 measured row(s) before)
…18 lost (engine, hardware) groups and 6 lowered figures in total
```

Per the repo rule (*"llgenie never patches upstream data to make a sync pass — a loss is reported
upstream and fixed there"*) the store is **not** vendored here: `data/models.json` stays at
2026-10-13, the derived artifacts are untouched, and the loss is filed as
andyholst/trending-local-llms#463. The weekly `registry-sync.yml` job lands the store once it is
additive again; no llgenie code change is needed for that step.

## What did land: the contract logic

- `scripts/model_engine_pick.py` — `FOOTPRINT_FIELDS`, `stated_gb()` (`5.95GB Q4_K_M` → 5.95,
  `800MB` → 0.78, `640GB NVMe, experts on SSD` → 640), `stated_context()` (`128K` → 131072,
  `1M` → 1048576), `footprint(model, measurement)` (measurement wins; absent stays absent),
  `stated_budget_gb()`.
- `fits(model, gb, ram_gb)` — a stated `system_ram_min` above this host's RAM excludes the model;
  `trend_list` / `recommend` / `offer` thread `ram_gb` through, so the list plain `llgenie` prints
  honours the floor.
- `rank_engines()` rows carry `footprint` (the run's own values); `_no_fit_reason()` cites the stated
  RAM floor and stated weights **before** any Hub file-size guess, and mentions `storage_offload`.
- `scripts/registry_keys.py` — `GROW_ONLY_SCALARS = ("weight_gb", "context_tokens", "system_ram_min")`:
  a lowered model-level value, or a measurement's lost/lowered own footprint, is a finding like a
  lowered t/s. A restated value (`5.95GB` → `5.95 GB`) is not.

## Verification

- `pytest tests/test_registry_footprint.py` → 12 passed (parsing, measurement-wins, RAM floor in
  `fits` and `trend_list`, engine-row footprint, reason text, four guard behaviours).
- `make check-registry-keys` → OK on the unmodified vendored store (23 models, additive only).
- `make check-registry`, `make check-wiring`, `make check-docs`, `make lint`,
  `make openspec-validate NAME=registry-contract-sync`, `make test-unit`.

## Honest limits

- The new data is not in this PR; nothing here has run against a real 50-model store — the fixtures
  carry the new fields, and the weekly sync will be the first real exercise. The functions are total
  over absent fields by construction (that is the case today's store exercises).
- `context_tokens` is read and carried, but the launcher's `-c` still derives from the GGUF header:
  the local-file path does not consult the registry. Separate change (noted as out of scope).
- Six new engines will need skill decisions when the store lands; `make engine-skill-gap` /
  `spawn-engine-skill-issues` already own that step, and no decision is invented here.
