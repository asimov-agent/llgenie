# Design notes

## What was ruled out, with the measurement

Two invariants that look like one:

```
#1063's gate     rows → fragments    no row without a fragment, no duplicate note
determinism      fragments → rows    committed table == render(fragments)
```

They are **duals, not duplicates**:

- **fragment-only** (add `docs/changes.d/<stem>.md`, do NOT regenerate `CHANGES.md`): leaves the
  committed table stale; the determinism test fails (measured on #1065 at `ed0b4cc5`). To allow
  it, the determinism test would have to relax to `committed ⊆ rendered`, which **permits a
  fragment with no row** — the published `CHANGES.md` silently omitting a change that happened.
  A missing published change is a defect in the artefact this repo publishes; a merge conflict is
  minutes of work (measured: `git checkout origin/main -- CHANGES.md && make changes-index` →
  267 fragments, 60 tests, all gates green). **Rejected.**
- **`.gitattributes merge=union`** on `CHANGES.md`: converts a loud conflict into a **quiet
  duplicate row** — disqualified (that is one of the two defects #1063's gate exists to catch; a
  union is a duplicate with nothing left to notice it beyond the gate).

## What remains in scope

The cost is real and merge-time-resolvable without touching the invariant. This change ships:

1. **a merge-time resolution helper** — `make changes-resolve` → takes main's file and
   re-renders (`git checkout <base> -- CHANGES.md && make changes-index`), then stages.
   Deterministic, no invariant change, removes the manual rebase work.
2. **an ordering/lock hint** — `docs/BOTS.md` documents that `CHANGES.md` is the one contended
   file and that the resolution is always "take base + re-render", so a lane resolves in one
   command instead of a rebase. (Docs, not a gate.)

Both keep `committed == rendered` true at every commit.

## Why `resolve` lives in `changes_index.py` and not a new script

A new `scripts/changes_resolve.py` would add a new document to the wiring graph (must be named by
a make target and reachable by CI, or recorded in `tests/fixtures/host-only-wiring.json`) and to
the `docs/ARCHITECTURE.md` census. `resolve` as a sibling subcommand of `check`/`render`/`write`/
`report` reuses the module's existing `render`, `_stems`, `CHANGES`, `REPO` and `subprocess` seam,
and the new test lives in `tests/test_changes_index.py` which is already wired and discovered. The
one new user-facing target `make changes-resolve` is documented in `docs/BOTS.md` (the automation
surface) and declared `.PHONY`.

## Semantics of `resolve`

Given a working tree whose `CHANGES.md` is conflicted (the file carries `<<<<<<<` markers), and a
`<base>` ref (default `origin/main`):

1. `git checkout <base> -- CHANGES.md` — replace the conflicted file with the base's version
   (both index and worktree).
2. re-render: `changes_index.write()` recomputes `CHANGES.md` from the merged fragments (both
   sides' fragment files merged cleanly — one row per file is the whole point), newest first.
   The renderer is idempotent, so the committed table is exactly `render(fragments)`.
3. `git add CHANGES.md` — stage the resolved file so the merge can complete.

The test proves a real two-commit conflict: two commits each add a fragment and a `CHANGES.md`
row, `git merge` produces a content conflict on `CHANGES.md`, `resolve` recovers, the file has no
conflict markers, equals the render, and the determinism test passes.
