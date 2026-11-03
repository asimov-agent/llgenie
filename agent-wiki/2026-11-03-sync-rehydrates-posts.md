# The sync rehydrates the counters and the footprint rows the 2026-10-31 store no longer carries inline (issue #687)

Upstream split its own store on 2026-10-31: `data/models.json` now carries **empty `engines[]`**
(the per-model t/s lives in `data/measurements.json`, keyed by model id), and the per-row engagement
counters (`likes/comments/reshares/views/interactions`) moved to a **new `data/posts.json`**, keyed by
the post URL. llgenie's `scripts/sync_registry.py` already rehydrated the t/s from `measurements.json`
back onto the engine rows, but it did **not** vendor `posts.json` at all, so every counter the
additive-only registry-keys gate reads off an engine row read as *gone* (799 losses on the live store).

The fix mirrors the existing `measurements.json` merge pattern: it vendors `posts.json`
(`UPSTREAM_POSTS`/`VENDORED_POSTS`) and rehydrates `likes/comments/reshares/views/interactions` onto each
engine row by its `source_post` URL. The t/s measurement merge itself sits in `_merge_measurements`
(#1678, merged on main first) keyed by `(engine, hardware)` so every distinct card run survives; this PR
keeps that shape and lays the counter rehydrate on top.

Measured on the live 2026-10-31 store against the committed one: `check-registry-keys` went from
**799 losses → 12**. The residual 12 are genuine upstream changes (posts removed outright, stated
footprints shrunk) that the additive-only guard is *designed* to refuse; AGENTS.md and #225 forbid
widening it, so they ride as expected removal/re-scape findings.

This PR is also the vehicle that carries upstream's **uzu** and **Inco Splash** decisions
(`data/unsupported-engines.json`, dated 2026-11-03, issue #1654): `make check-engine-skill-gap` exits 0
(45 engines / 16 shipped / 29 known-unsupported / 0 unresolved) against the synced 45-engine registry.
`tests/fixtures/trend-list-matrix.json` + `hub-snapshot.json` were regenerated against the real store
(`make render-trend-list-matrix`). The quant catalog (`data/trending-quant-catalog.json` + its
`quant-catalog-hub-snapshot.json`/`trending-quant-catalog.json` fixtures) is re-synced from the same
store (`make sync-quant-catalog`) so its HF-tree lookups cover the newly added models —
`check-quant-catalog` is hermetic green (`#1178`).

References: #687 (this change), #1634 (the measurements.json rehydrate precedent), #1654 (the
uzu/Inco Splash decisions), #1649/#1678 (the (engine, hardware) run-survival key), #229 (the
unsupported-engines decision file), AGENTS.md "the vendored registry is additive only".
