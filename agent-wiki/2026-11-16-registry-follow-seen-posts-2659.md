# 2026-11-16 — follow the fixed trending store: seen_posts retention rehydration (issue #2659)

## What was verified

- The `registry-sync` weekly lane failed four consecutive runs (2026-11-13 … 2026-11-15) with
  `24 loss(es) vs HEAD:data/models.json` — "gone from the store" tracked-post findings.
- Root cause is upstream **policy**, not breakage: `andyholst/trending-local-llms`
  `scripts/update_trending.py::prune_posts` (`RETENTION_DAYS = 30`) prunes each model's
  `engagement.seen_posts` on every merge ("the model row is never removed — only its stale post
  history is pruned"), and a post outside the window that was not re-seen is absent from upstream
  `posts.json` and `measurements.json` too. llgenie's additive-only guard tracks every
  `/status/<id>` post across `engines[]` **and** `engagement.seen_posts` and may never be widened,
  so the windowed store could not pass while the guard stayed fixed.
- The seam now carries instead: `scripts/sync_registry.py::_rehydrate_seen_posts` unions post
  identity store-wide, keeps the new store's fresher entry, appends a carried post to the surviving
  row that previously held it, keeps re-attributed posts exactly once, never resurrects a removed
  model row, and never carries placeholder entries (no `/status/<id>` — derived state upstream
  rebuilds from measurements). Third rehydrate of the #687 (post counters) / #1634 (measurements)
  pattern.
- `make sync-registry` vendored the 2026-11-15T08:29:53Z store: 117 → 118 models (+`alpie-seed-9b`,
  8GB MLX), tracked post ids 427 -> 445, 34 retention-pruned posts carried with notes
  (seam replay at the 2026-11-15 blobs: 34 `carried retention-pruned post:` notes, rc=0).
- `make check-registry` rc=0 and `make check-registry-keys` rc=0 —
  "OK: additive only — nothing lost vs HEAD:data/models.json (118 models, 299 note(s))" — where the
  weekly lane had logged 24 losses. The guard itself was NOT widened; only the 24→0 loss arithmetic
  changed.
- Derived tables re-rendered green: `render-trend-list-matrix`/check (81 cases),
  `render-engine-skill-gap`/check (46 engines, 17 skills, unresolved 0, never-offered models 12),
  `sync-quant-catalog`/check (93 models, 2121 links, +325 additive), `skills-validate` 0 errors.
- 5 new tests (`tests/test_registry_seen_posts_rehydration.py`) pin the spec scenarios, including
  guard-red-before-carry → guard-green-after-carry and removed-model-row-stays-a-guard-failure.

## Key decisions

- Rehydrate at the vendor seam rather than exempt seen_posts from the guard: the guard's purpose
  (nothing tracked disappears) stays intact, and carry-forward beats waiting for a post to be
  re-sighted.
- Placeholders are never carried; a removed model row is never resurrected — both keep upstream
  deletions loud.
- No llgenie-side change mirrors the upstream retention constant (the guard stays loss-blind and
  additive-only). Upstream's own follow-up to publish pruned post history into its posts ledger is
  tracked upstream (trending-local-llms issue #1080); when that lands, carried entries and store
  entries merge by identity without a duplicate.

## Current status

Issue #2659 drives the change; the PR lands it once CI is green and armed. The next scheduled
`registry-sync` run (Wednesday 18 Nov) should now pass on main without exemption drift.
