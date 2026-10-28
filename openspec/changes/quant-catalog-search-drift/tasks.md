# quant-catalog-search-drift — Tasks

Issue: [#769](https://github.com/asimov-agent/llgenie/issues/769)

- [x] 1. `compare()` probes a dropped plan's link and fails only on `dead` (404/410); `ok`/`gated` is a note naming the plan and the status.
- [x] 2. `carry_over()` re-inserts a still-reachable committed plan into a sync's table and returns the `kept`/`dropped` lines.
- [x] 3. `main()` runs the carry-over on generate (never on `--check`) and prints `[sync] kept …` / `[sync] dropped …`.
- [x] 4. `tests/test_quant_catalog_compare.py` locks both outcomes through the real `compare()`/`carry_over()` and the unpatched `_probe_status()` against a real loopback HTTP server (200 / 401 / 404) — no mocks.
- [x] 5. The three existing tests that asserted the old "no longer generated" verdict are updated to the split rule (dead fails, reachable is a note), plus the changed-plan pair.
- [x] 6. `make check-quant-catalog`, `make test-unit`, `make lint`, `make check-wiring`, `make check-docs`, `make openspec-validate NAME=quant-catalog-search-drift` pass.
