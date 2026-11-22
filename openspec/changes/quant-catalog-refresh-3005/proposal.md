# Quant catalog refresh (issue #3005)

## Why

The `ci-hf-live` battery is red on `main` (run `45010151478` at `46b15838e1`): its `check-quant-catalog LIVE=1` step reports the committed `data/trending-quant-catalog.json` is not fresh against a live regeneration — it first named the `qwen3.8-27b / llama.cpp (PrismML fork)` plan `Qwen3.8-27B-UD-IQ2_S.gguf` as gone, and a fresh local replay named `qwen3.8-27b/vLLM` `Qwen3.8-27B-UD-Q6_K_L.gguf` (a transient Hub 404; the file answers 302 again minutes later). Meanwhile the live trending build carries a new quant repository (`nace-ai/Qwen3.8-27B-MLX`) the committed catalog never saw. Per the post-merge live-verification rule, a red battery is fixed by a data refresh, not by re-runs.

## What Changes

- Re-run the mandated refresh chain on the committed data: `make -s sync-registry` → `make -s sync-quant-catalog` → `make -s render-trend-list-matrix` → `make -s render-engine-skill-gap` → `make -s skills-validate` (the AGENTS re-pin render order).
- Land the resulting data deltas: `data/models.json`, `data/trending-README.md`, `data/trending-quant-catalog.json` (adds the `nace-ai/Qwen3.8-27B-MLX` repo rows; keeps still-reachable plans the live search no longer returns) and the recorded Hub fixtures `tests/fixtures/trending-quant-catalog.json`, `tests/fixtures/quant-catalog-hub-snapshot.json`, `tests/fixtures/hub-snapshot.json`.
- No unskilled engines arrive (gap check: registry 50 engines, 18 skills, 0 unresolved), so `spawn-engine-skill-issues` files nothing new.
- Prove the battery's own gate green on the refreshed tree: `make check-quant-catalog` (hermetic) and `make check-quant-catalog LIVE=1` (the ci-hf-live seam).

Out of scope (filed as a linked issue): the freshness gate classifies a transient Hub 404/5xx/transport probe as a permanently dead plan, so one flaky probe can redden the battery. Probe retry policy is a separate change.

## Impact

- Data: `data/models.json`, `data/trending-README.md`, `data/trending-quant-catalog.json`
- Fixtures: `tests/fixtures/trending-quant-catalog.json`, `tests/fixtures/quant-catalog-hub-snapshot.json`, `tests/fixtures/hub-snapshot.json`
- Gates: `check-quant-catalog` (hermetic + `LIVE=1`), `check-trend-list-matrix`, `check-engine-skill-gap`, `skills-validate`
- No code, no workflow changes.
