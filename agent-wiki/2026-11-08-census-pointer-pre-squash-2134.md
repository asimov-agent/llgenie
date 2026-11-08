# Fix: main was red on `check-docs` — census pointer named a pre-squash commit (#2134)

## What changed

Repointed `docs/ARCHITECTURE.md`'s architecture census from `605f1a2e` to `2e04c9c2`, and re-measured
every census number at that sha with `git ls-tree -r --name-only` rather than copying the old values.

**`main` was red on `make check-docs` before this change** — verified on a clean detached checkout of
`2e04c9c2` with no local changes:

```
[census-gate] the census has no usable referent — census measured at `605f1a2e`
  (tracked=3730, testspp=231, changes=375); no usable referent; HEAD is 2e04c9c2
make: *** [Makefile:1022: check-docs] Error 1
```

## Why the pointer was invalid

`605f1a2e` is a **pre-squash commit on the PR branch**, not the commit that landed:

```
git merge-base --is-ancestor 605f1a2e 2e04c9c2   → NO
git branch -r --contains 605f1a2e                → origin/agent/issue-795-scripts-layering-data
```

The census gate's own docstring documents this hazard — the pointer must be an ancestor of `HEAD` so the
census is reproducible from a tree the branch actually contains, and *"a pointer naming its own branch
head no longer dangles once the PR is squashed"*. The gate was correct; the document was not.

## Numbers corrected (all re-measured at `2e04c9c2`)

| claim | was | now |
|---|---|---|
| tracked files | 3,721 | **3,730** |
| `openspec/` | 1,463 | **1,467** |
| `agent-wiki/` | 645 | **647** |
| `docs/` | 654 | **656** |
| `openspec` changes | 374 | **375** |
| `tests/test_*.py` | 231 | 231 (unchanged) |

Note the old numbers were *also* wrong for main: they were measured at the pre-squash commit, which
carries a different tree. Only the pointer fix plus a re-measure makes them true.

## Why this mattered

While main was red, the **entire docs gate was unenforced** — the change-note trio, the README target
sweep, the `CHANGES.md` index check and the census itself all stop running. Every PR cut from main
inherited the red. This was the highest-severity finding of the #2117 docs audit.

## Recurring class — the durable half is the code lane's

Closed predecessors: #1051, #1221, #1236, #1246. Each was fixed by editing the document; each recurred.
The durable fix is that whatever writes that pointer must derive it from the **squash commit that
landed**, never from the PR branch head — a `scripts/` change, recorded in #2134 for
`@llgenie-ci-pipelines-maintainer`. This PR is the docs half only.

## Files

- `docs/ARCHITECTURE.md` (census sentence + two table cells)
- `docs/changes.d/2026-11-08-census-pointer-pre-squash-2134.md`
- `agent-wiki/2026-11-08-census-pointer-pre-squash-2134.md` (this note)
- `CHANGES.md` (regenerated index)

No `scripts/`, `tests/`, workflow or Makefile change.
