# Proposal: trend-list-matrix-rerender-3056

## Why

`tests/fixtures/trend-list-matrix.json` is the committed answer to "which model does the pick choose
in each (engine, VRAM band, host-RAM) cell". The hermetic contract check replays the recorded Hub
answers in `tests/fixtures/hub-snapshot.json`, so a fixture that matches its own recording stays green
even after the live trending moved under it. The staleness read shipped in the #2901 lane
(`make check-trend-list-fresh`) measured that drift on the newest `main` run and filed it as issue
#3056: 4 cells disagree, all `metal/24/*` (fixture -> live):

- `metal/24/8`, `metal/24/32`, `metal/24/60`, `metal/24/64`: changed Gemma 3 27B (why: smallest GGUF is
  6 GB > 10 GB this host can hold -> smallest GGUF is 10 GB > 10 GB this host can hold)

The drift is why the `ci-hf-live.yml` battery on `main` is red today (`post-merge-live-check` reports
`ci-hf-live.yml run=45381621908 event=schedule conclusion=failure`), and a red battery blocks every
post-merge verification landing depends on (issue #2900 discipline).

## What Changes

- Re-render the trend matrix from the LIVE trending in the order the post-merge rule fixes
  (`docs/post-merge-live-verify.md` step 5): `make -s sync-registry` -> `make -s sync-quant-catalog` ->
  `make -s render-trend-list-matrix` -> `make -s render-engine-skill-gap` -> `make -s skills-validate`,
  so `tests/fixtures/trend-list-matrix.json` and `tests/fixtures/hub-snapshot.json` agree with the same
  live read on one commit.
- Keep the re-render a data-only change: the fixture+snapshot pair and the `docs/trending-*.md`
  fragments it rewrites are the whole delta; no gate, picker or monitor behaviour changes.
- Land it as its own feature branch + PR referencing issue #3056 so the fixture delta is reviewable,
  and close the drift the moment `make check-trend-list-fresh` reads green on `main` after the merge.

## Impact

- Affected specs: `trend-list-matrix`
- Affected code: `tests/fixtures/trend-list-matrix.json` and `tests/fixtures/hub-snapshot.json`
  (the rendered pair), plus the inputs the fixed order re-pulls — `data/trending-README.md`,
  `tests/fixtures/quant-catalog-hub-snapshot.json` and `data/engine-skill-gap.json` — all render
  outputs only
- Affected gates: `make check-trend-list-matrix`, `make check-trend-list-fresh`,
  `make skills-validate`, `make test-unit`
