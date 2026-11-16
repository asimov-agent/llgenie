# llgenie follows the 2026-11-15T08:29:53Z trending store

## Why

The weekly `registry-sync` lane has failed four runs in a row (11-11, 11-14 ×2, 11-15):
`check-registry-keys` refuses the store because tracked posts are "gone from the store". llgenie
still vendors the **2026-11-04T15:29:04Z** store (117 models), so every weekly run starts from
11-04 and re-fails. Issue #2659 is the change-issue the lane filed for the newer store; no sync
PR ever merged.

The root cause is measured, and it is not upstream breakage: upstream's producer applies a
documented **retention policy** — `trending-local-llms/scripts/update_trending.py::prune_posts`
drops `engagement.seen_posts` entries older than `RETENTION_DAYS = 30` on every store merge
("the model row is never removed — only its stale post history is pruned (AGENTS retention)"),
and a pruned post that was never re-seen inside the window is not carried into `data/posts.json`
either. Measured against upstream master `bfcff459f` (store `2026-11-15T08:29:53Z`, 118 models):

- `models.json` status URLs: **427 (vendored 11-04 store) → 411**, i.e. **34 tracked posts are
  gone from the store** (counting method: unique `/status/<id>` matches over the whole
  `models.json` text, both files).
- Of those 34, only **1** survives anywhere (in `posts.json`/`measurements.json`); the other
  **33** are absent from all three vendored-pair files — retention removed them outright.
- The rest of the store is clean additive: 117 → 118 models (+`alpie-seed-9b`, shipped, MLX),
  26 model-level engines unchanged, contract pair byte-identical, `posts.json` 360 → 375 with
  **zero** of the 360 vendored URLs dropped, `measurements.json` 357 → 357 status URLs, zero
  losses.

llgenie's additive-only guard (#233/#668) tracks every `/status/<id>` across `engines[]` AND
`engagement.seen_posts` and is forbidden from widening ("never widen this file"). Its own spec
makes a post nowhere in the new store a fatal loss — so upstream's windowed trending view can
never be vendored while the guard keeps its teeth, and the guard is right to keep them.

The fix is the **established vendor-seam rehydrate pattern** (issue #687/#1634/#1678 precedent:
`sync_registry.py` already rehydrates `measurements.json` t/s onto engine rows and `posts.json`
counters onto rows precisely so the gate sees what it reads). The third departure of the same
kind: the sync carries `engagement.seen_posts` entries that upstream's 30-day retention pruned
out of the **previous vendored copy** (the durable ledger llgenie owns) into the new rows,
keyed by post identity, new entries winning. Retention windows upstream's trending view; it must
not delete posts from llgenie's ledger.

## What changes

1. **`scripts/sync_registry.py` gains the retention rehydrate.** After the measurements and
   counters rehydrates, the sync unions the previous vendored rows' real-URL `seen_posts`
   entries into each surviving row by `/status/<id>` post identity: fresher entries win, carried
   entries are appended, a post re-attributed to another surviving row is never duplicated, and
   a gone model row is never resurrected (the guard must still fail on a removed model row).
2. **The vendored store becomes the 11-15 store**: `make sync-registry` rewrites
   `data/models.json`, `data/posts.json`, `data/measurements.json` and `data/trending-README.md`
   through the seam; `make check-registry-keys` then reports `OK: additive only` (the 34 are
   carried, not widened away) — every loss the guard can still see stays fatal.
3. **Derived tables are regenerated from it, never hand-edited:** `make sync-quant-catalog`,
   `make render-trend-list-matrix`, `make render-engine-skill-gap` (46 engines unchanged).
4. **No engine decision is needed:** the one new model names only `MLX`, a shipped skill, so
   `data/unsupported-engines.json` is untouched and `check-engine-skill-gap` stays green.
5. The guard `scripts/registry_keys.py` is **not touched** — no exemption, no widening.

## Impact

- Code: `scripts/sync_registry.py` (one seam function + call + notes), `tests/test_registry_seen_posts_rehydration.py`.
- Data: `data/models.json`, `data/posts.json`, `data/measurements.json`, `data/trending-README.md`,
  `data/trending-quant-catalog.json` + fixture, `tests/fixtures/trend-list-matrix.json` +
  hub-snapshot, `data/engine-skill-gap.json`, README-link/measurements fixtures that follow the store.
- Docs: README registry/guard section documents the third rehydrate; `agent-wiki/` entry;
  `docs/changes.d/` fragment. Upstream issue `andyholst/trending-local-llms#1080` gets the root
  cause (retention) and the consumer-side resolution.
- Out of scope (separate linked issues): the producer-side durable ledger (pruned posts should
  land in upstream `posts.json` — upstream #1080), and the guard's pairing scan (consulting
  `posts.json`/`measurements.json` for a gone post) if upstream keeps posts out of the store
  entirely — not needed once the seam carries them.
