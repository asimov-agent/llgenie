---
openspec: architecture-census-gate/architecture-census-gate
---

# 2026-10-29 — issue #896: the architecture census is now a gate, so a drift cannot go silent

## What was wrong

`docs/ARCHITECTURE.md` states a census of the tree ("The tree is N tracked files …"), and nothing
checked it. It drifted at least twice in two days — most recently to the point of being ~375 files
behind the tree (doc said 1576 tracked files when the tree held 1951, and `docs/` 7 when it held 243,
because the fragment regime moved the change index under `docs/changes.d/`). Each time a lane or a
reviewer found it by hand.

## What the change is

`make check-architecture-census` parses the census sentence and the two count cells out of
`docs/ARCHITECTURE.md`, counts `HEAD` with `git ls-tree -r --name-only`, and fails when they disagree —
naming both values and the sha it measured. It is wired into `check-docs`, so the docs gate is the
place a drift stops being silent. The census is corrected to the current tree with a `measured at <sha>`
note, so the numbers are reproducible.

## Decisions

- **`git ls-tree` is the counter, not a directory walk** — `git ls-tree -r --name-only HEAD` is what a
  census means ("tracked files"), and it is the same call the architecture bot and the audit script use,
  so lanes can't disagree about the number.
- **The gate checks counted facts only** — the prose claims are `architecture-bot`'s regeneration scope
  (#896 "Not covered"), which is the same boundary as the doc's own generator.

Measured at `348f7b4e`: 1966 tracked files; data 9, skills 17, containers 57, tests 199, scripts 118,
openspec 1019, agent-wiki 239, docs 246; `tests/test_*.py` 169; openspec changes 261.

Issue: #896, #1033
