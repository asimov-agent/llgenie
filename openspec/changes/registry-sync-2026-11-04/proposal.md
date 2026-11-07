# llgenie follows the 2026-11-04T15:29:04Z trending store

## Why

The weekly `registry-sync` published a new vendored store — `generated_utc`
`2026-10-31T00:23:05Z` -> `2026-11-04T15:29:04Z` — while llgenie was still built to the old one:
`data/models.json` was the previous store, `data/engine-skill-gap.json` still counted 45 engines,
the quant table still carried the old 1764 links and the trend-list matrix was still the one
rendered from the old row set. A product reading yesterday's catalogue offers no new model, cannot
rank an engine nobody taught it about, and its golden tests keep passing against rows upstream has
already replaced — nothing fails until a model is noticed missing.

The store is 117 models before and after, **one** engine new to the registry (`Surogate`), the
quant catalog 93 models / 1764 -> **1796** links, and the contract unchanged (no required key added
or removed, no new `backend`).

## What changes

1. **The vendored store is the new one.** `make sync-registry` rewrites `data/models.json` and the
   README it is read with, from the upstream master both the job and this change read.
2. **Every derived table is regenerated from it**, never hand-edited: `make sync-quant-catalog`
   (93 models / 1796 links) and `make render-trend-list-matrix` (81 cases) plus
   `make render-engine-skill-gap` (46 engines, 16 shipped).
3. **The one engine new to the registry is decided, not carried silently.** `Surogate` is a
   C++/CUDA native server (invergent-ai/surogate, Apache-2.0) auto-registered from a single
   announced tweet with one stated run (Qwen3.8-Flash-Next 125B at 35.2 t/s on RTX 5090,
   2026-11-01) and no llgenie skill/image yet; it gets a dated `deferred` decision in
   `data/unsupported-engines.json` (ship tracked in #1962) so `make check-engine-skill-gap`
   reports `unresolved 0`. The rule #229 exists for exactly this: a just-listed engine with no
   artifact ages into the ship queue instead of blocking the store.

## Impact

- Data: `data/models.json`, `data/trending-README.md`, `data/trending-quant-catalog.json` + its
  fixture, `tests/fixtures/trend-list-matrix.json`, `data/engine-skill-gap.json`,
  `data/unsupported-engines.json`, plus the measurements/posts/README-link/hub-answer fixtures that
  follow the store.
- No script, no engine skill, no image changes: the store moved, the code that reads it did not.
- `agent-wiki/` note + `CHANGES.md` row.
