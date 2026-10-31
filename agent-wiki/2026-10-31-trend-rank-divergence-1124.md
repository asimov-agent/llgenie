# trend_rows now serves the same engine rank_engines picks (matrix == ranking)

Issue: #1124.

`trend_rows` (the `llgenie --matrix` table, committed golden `tests/fixtures/trend-list-matrix.json`)
and `rank_engines` (the ranking the picker uses) disagreed for the same model+host: the ranking
correctly picked `llama.cpp (PrismML fork) @ 128 tps` on cuda while the matrix served the phone's
plain `llama.cpp @ 6.0` cpu row.

Root cause: `model_engine_pick.engine_supported_quants` gates a cell by `arch not in supported`,
comparing the host arch against the catalog's `arch` list literally. That list is the engine's
IMAGE-VARIANT archs (prism: `[vulkan, cpu, metal]` — no cuda image), but `rank_engines`/`host_engines`
resolve runnability with the cpu fallback (`variant = arch if arch in variants else cpu`), so prism IS
runnable on a cuda/rocm host through its cpu image. The matrix therefore dropped the very engine the
ranking ranked first, and the golden recorded a row the ranking would never choose.

Fix: the catalog arch gate now applies the same variant resolution as the ranking — an engine whose
`cpu` image is runnable on a card host is offered there. The regenerated fixture (49 card-host cases,
669 rows) now matches `rank_engines[0]` for every moved row (0 disagree), the model set is unchanged,
and cpu/metal rows moved not at all (cpu-fallback does not apply there). `make render-trend-list-matrix`
+ `make check-trend-list-matrix` green; the matrix comparison (`@network`) passes 81/81.

`generated_utc` is unchanged so the fixture is still the vendored registry 2026-10-27 store.
