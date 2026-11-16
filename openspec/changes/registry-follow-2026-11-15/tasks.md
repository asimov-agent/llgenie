# Tasks

- [x] 1. OpenSpec change written: proposal (measured retention root cause: 34 gone posts, 33 of 34 absent from all three pair files) + `specs/registry-sync-store/spec.md` + this checklist.
- [x] 2. `scripts/sync_registry.py` gains `_rehydrate_seen_posts(rows, previous_rows)` wired after the counters rehydrate: carry real-URL `seen_posts` posts from the previous vendored copy by `/status/<id>` identity; fresher entry wins; no cross-row duplicates; gone rows never resurrected; placeholders never carried. `scripts/registry_keys.py` untouched.
- [x] 3. `tests/test_registry_seen_posts_rehydration.py` — the five spec scenarios, one test each.
- [x] 4. `make sync-registry` writes the 2026-11-15 store through the seam: `generated_utc` `2026-11-15T08:29:53Z`, 118 models, posts 360 -> 375, all 34 retention-pruned posts carried (`data/models.json`, `data/posts.json`, `data/measurements.json`, `data/trending-README.md`).
- [x] 5. `make check-registry` + `make check-registry-keys` are green: `OK: additive only` vs `HEAD:data/models.json` / `HEAD:data/posts.json` with zero loss findings.
- [x] 6. `make sync-quant-catalog` rewrites `data/trending-quant-catalog.json` + its fixture and `make check-quant-catalog` is green.
- [x] 7. `make render-trend-list-matrix` rewrites `tests/fixtures/trend-list-matrix.json` + hub-snapshot and `make check-trend-list-matrix` is green.
- [x] 8. `make render-engine-skill-gap` rewrites `data/engine-skill-gap.json` (46 engines unchanged, unresolved 0) and `make check-engine-skill-gap` is green.
- [x] 9. `make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json` is green.
- [x] 10. `make test-unit` is green with the goldens re-derived for the new row set.
- [x] 11. Docs in the same batch: README registry/guard paragraph on the third rehydrate, `agent-wiki/2026-11-16-registry-follow-seen-posts-2659.md`, `docs/changes.d/2026-11-16-registry-follow-seen-posts-2659.md` fragment; upstream issue `andyholst/trending-local-llms#1080` gets the retention root cause + consumer-side resolution comment.
- [x] 12. `make openspec-validate NAME=registry-follow-2026-11-15` exits 0; `make lane-preflight` prints `preflight: OK`; branch pushed; PR open against `main` closing #2659 with measured rc= proofs, and the #2659 body mirrors this change.
