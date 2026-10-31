# Coupling an engine params/arch change to the trend-list-matrix re-pin (#1232)

## What

`scripts/engine_skills.py` generates per-engine params and validates them on the
committed tree (`make check-engine-params`, `pipeline.yml:92`). But **nothing
forced `make render-trend-list-matrix` to run and re-pin
`tests/fixtures/trend-list-matrix.json` + `tests/fixtures/hub-snapshot.json`
when an engine's params or its supported-arch set changed.** The two fixture
gates are hermetic against the committed fixture (`scripts/trend_list_matrix.py
--check`, issue #1080), so:

- a params/arch delta that **textually** shifts the matrix rows already reds
  `check-trend-list-matrix` (tested: unchanged engines re-verify cleanly); but
- a delta that leaves the rows **byte-identical** — an engine gains a variant
  the matrix endpoint can already serve, or the change re-pins only the
  engine→variant map — landed green through every gate, with no step naming the
  re-render. The add-engine/params path had no forcing step (verified: adding a
  `vulkan` variant to vLLM left `trend_rows()` unchanged byte-for-byte).

## The guard

`scripts/trend_list_matrix.py` now records an **`engine_variant_fingerprint`**
in the committed fixture: sha256[:16] of the exact engine→sorted-variants map
`model_engine_pick.engine_ids()` returns (read from
`containers/engines/params/*.json`). `build()` embeds it; `--check` compares it
to the committed value, so:

- a params/arch delta that changes the matrix-consuming engine→variant map
  (an engine added/removed, an arch/variant gained or lost) makes the recorded
  fingerprint stale → `check-trend-list-matrix` fails naming
  `make render-trend-list-matrix`, **even when no row text moved**;
- the render path writes both fixtures in one run (still hermetic: `--check`
  replays `tests/fixtures/hub-snapshot.json`, never the live Hub), so
  re-pinning the two fixtures in the same change closes the seam;
- a cosmetic params edit that does **not** change the engine→variant map leaves
  the fingerprint untouched and forces no re-render (acceptance: "possibly
  empty-on-no-op re-pin").

No engine params were changed; only a guard/coupling on `trend_rows`'s caller
and the fixture's recorded stamp. `check-trend-list-matrix` semantics are
strictly MORE coupled (the fixture must now also match the params tree), never
less (issue #1080 preserved).

## Verification

- Arch delta (vLLM + `vulkan`): `python3 scripts/trend_list_matrix.py --check`
  exits 1 → `… is stale. Run make render-trend-list-matrix.`
- Clean tree: exits 0 (`OK … 81 cases, recorded tests/fixtures/hub-snapshot.json`).
- `python3 -m pytest tests/test_trend_list_matrix.py -m "not network"` → 5 passed
  (hermetic pins + the new fingerprint guard).
- The committed-fixture diff is exactly one added `engine_variant_fingerprint`
  key; every row is byte-identical (a re-render produced no other change).
