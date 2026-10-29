# llgenie follows the 2026-10-27T21:47:11Z trending store

## Why

The weekly `registry-sync` published a new vendored store — `generated_utc`
`2026-10-27T12:53:42Z` -> `2026-10-27T21:47:11Z` — while llgenie was still built to the old one:
`data/models.json` was the previous store, `data/engine-skill-gap.json` still counted 42 engines,
the quant table still carried the old 1611 links and the trend-list matrix was still the one
rendered from the old row set. A product reading yesterday's catalogue offers no new model, cannot
rank an engine nobody taught it about, and its golden tests keep passing against rows upstream has
already replaced — nothing fails until a model is noticed missing.

The store itself is additive: 112 models before and after, **one** engine new to the registry
(`Rapid-MLX`), the quant catalog 89 models / 1611 -> **1661** links, and the contract unchanged
(no required key added or removed, no new `backend`). `make check-registry-keys` confirms nothing
was lost.

## What changes

1. **The vendored store is the new one.** `make sync-registry` rewrites `data/models.json` and the
   README it is read with, from the upstream master both the job and this change read.
2. **Every derived table is regenerated from it**, never hand-edited: `make sync-quant-catalog`
   (89 models / 1661 links; 0 links newly added on this store, so the live-Hub probe validated
   nothing and gated nothing) and `make render-trend-list-matrix` (81 cases) plus
   `make render-engine-skill-gap` (43 engines, 16 shipped).
3. **The one engine new to the registry is decided, not carried silently.** `Rapid-MLX` is an
   Apple-Silicon-only MLX server (Homebrew/PyPI, pure MLX kernels, no Linux or GGUF path) whose
   product is a macOS desktop app plus image/video/audio aliases; Metal cannot run in llgenie's
   Linux image and that platform is already served natively by the `mlx` engine, so it gets a dated
   `deferred` decision in `data/unsupported-engines.json` read from upstream's own README — the rule
   #229 exists for. `make check-engine-skill-gap` reports `unresolved 0`.

## Impact

- Data: `data/models.json`, `data/trending-README.md`, `data/trending-quant-catalog.json` + its
  fixture, `tests/fixtures/trend-list-matrix.json`, `data/engine-skill-gap.json`,
  `data/unsupported-engines.json`.
- No script, no engine skill, no image changes: the store moved, the code that reads it did not.
- `agent-wiki/` note + `CHANGES.md` row.

Not in this change: the ranking rule the trend list is built on (#669 — the trend list is *reported*
here, its gate is not chosen here), and building an image for `Rapid-MLX` should a later decision
promote it to a native Metal engine (its own work item, per AGENTS.md).
