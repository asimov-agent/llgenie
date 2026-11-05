# Upstream registry store sync (`data/**`, `scripts/sync_registry.py`)

For issues where the deliverable is re-vendoring an upstream registry snapshot into
llgenie and satisfying the additive-only gates.

## Procedure

1. **Diff raw upstream against raw upstream, not the vendored snapshot against HEAD.**
   Pull the live upstream files and inspect their *shape* first. Upstream periodically
   re-splits its store: per-model throughput moves into `measurements.json`, per-post
   engagement (`likes`/`comments`/`reshares`/`views`/`interactions`) moves into a new
   `posts.json` keyed by post URL, and `models.json` `engines[]` rows come back nearly
   empty. A guard reporting "N keys lost" almost always means the sync stopped
   vendoring a *new* file — an in-tree fix — not that upstream deleted data. Prove it by
   grepping the raw upstream tree for the vanished fields.
2. **Vendor every upstream file the sync reads, in the same commit.** Add the path
   constant beside the existing vendored ones and mirror the existing merge pattern
   (`POST_COUNTERS` next to `MEASUREMENT_FIELDS`), rather than inventing a second style.
3. **Key each merge by the identity the data is actually per-X on.** Measurement rows
   are per `(engine, source_post)`; keying by `engine` name alone collapses distinct
   post rows and silently drops the footprint fields (`context_tokens`, `weight_gb`,
   `system_ram_min`, `engine_min_version`, `storage_offload`) that only the later rows
   carried. Before committing, count unique values on both candidate keys — if
   `len(rows) != len({key})` the key is too coarse.
4. **Preserve the existing JSON key order.** Re-serializing with `sorted()` reorders
   every pre-existing key and turns a two-entry addition into a 160+ line diff; the
   additive guard and the reviewer both read that as mass churn. Insert new entries
   in place and leave the rest byte-identical — the diff must be pure insertions with
   zero deletions. Check with `git diff --numstat` (`N 0 file`) before committing.
5. **Regenerate every derived artifact last.** `data/engine-skill-gap.json`,
   `data/trending-quant-catalog.json` + `tests/fixtures/quant-catalog-hub-snapshot.json`,
   `tests/fixtures/{readme-link-answers,trend-list-matrix,hub-snapshot}.json` and the
   README answers are generated from the store. Rendering them before the store is
   final leaves them stale and their "is current" tests red at head even though the
   store itself is correct. Order: sync → fix the merge → re-sync → render every
   generated file → run the suite → one commit. If the branch is unpushed or yours
   alone, fold the correction in with `--amend` and push with `--force-with-lease`
   rather than adding a "fix stale fixture" commit.
6. **Classify the residual losses; never widen the guard.** The additive-only guard
   refuses any tracked post or key that disappears. Split the remainder into
   (a) rehydratable — the key still exists upstream somewhere, fix the sync;
   (b) representation change — the value moved file; (c) genuine upstream removal or
   shrunk footprint. (c) is reported upstream, never absorbed (AGENTS.md: never widen
   that file). A small residual with a documented per-item cause is a legitimate PR
   state; hand-editing the guard is not. Cite the per-item classification in the PR
   body so a reviewer can check it.
7. **Run the gates in this order:** `make check-registry-keys`,
   `make check-engine-skill-gap`, `make check-registry`, `make check-docs`, then
   `make test-unit`. `test-unit` is containerized and long — run it as a background
   process and poll, never in a foreground call with a short timeout. For a store
   change `test-unit` is the real acceptance; the weekly job's `check-registry` may
   stay red on the documented residual and that is not a blocker for the PR.
8. **New engines need dated decisions.** Take the unresolved engine names from the
   `check-engine-skill-gap` output itself (the registry `engines` list is the
   authority), then add entries to `data/unsupported-engines.json` with `decided`
   and a `note` that cites the issue. Re-render the gap file afterwards and confirm
   `0 unresolved`.
9. **Expect the change→note→fragment trio; prove it with the gate, not from the path list.**
   A store re-sync changes committed data that the docs/gap generators read, and a behaviour
   change under `scripts/` owes the trio too. Do not assume exemption from the issue's scope
   sentence — run `make check-docs` at the committed head and add the note + one-row fragment +
   rendered `CHANGES.md` row if it fires. See `change-note-fragment-trio.md`.

## Pitfall: a model added by the sync reds `check-quant-catalog`, and the cure is its OWN sync

`check-quant-catalog` resolves each model's HF tree through its own recorded snapshot
(`tests/fixtures/quant-catalog-hub-snapshot.json`), NOT the `hub-snapshot.json` the trend-list
render writes. A store sync that adds a model therefore reds with

```
HubSnapshotMissing: [<org>/<model>]
```

even when every trend-list/hub fixture is current. `make render-trend-list-matrix` will not fix
it — it records only its own answers. Run `make sync-quant-catalog`, which regenerates the
catalog and writes its snapshot together (the same "catalog ships with its snapshot" rule the
generator enforces), then re-run `make check-quant-catalog`.

This red is easy to miss locally because `linux / unit` runs the targets sequentially
(`test-unit` → `check-registry` → `check-strata-models` → `check-quant-catalog`): while `test-unit`
is red, make never reaches `check-quant-catalog` and the missing-model failure stays invisible until
the earlier leg goes green. When a store change adds models, run the full target list before
believing a green.

## Reporting

The PR body should name: the upstream re-split that caused the problem, the merge
key, the before/after loss count, the test-unit totals at head, and the per-item
classification of what remains.
