# llgenie — #2167: docs(architecture) refresh for the tree at 20261108T0651

- **Date:** 2026-11-08 · **Issue:** #2167 (architecture refresh drift)
- **Branch:** `agent/architecture-20261108T0651` (census measured at `7ef346c8`)
- **PR:** the ready-for-review PR #2167

## What changed

`docs/ARCHITECTURE.md` lagged the tree — its previous census was measured at `2e04c9c2`. The
architecture refresh re-derived the census from real `git` state and updated the repository-layout
counts to the tree at `7ef346c8` (3763 tracked files: `data/` 13, `skills/` 17, `containers/` 57,
`tests/` 274, `scripts/` 164, `openspec/` 1478, `agent-wiki/` 653, `docs/` 662), the openspec
change count (378) and agent-wiki entry count (653), the `test-unit` file count (208→215), and the
engine-skill census (46 engines, 30 known-unsupported vs 0 unresolved). It also added the
`data/verdict-roster.json` note (issue #2116) and replaced date-stamped store phrases ("the
2026-11-07 store") with "the current store". This PR carries only `docs/ARCHITECTURE.md`, plus this
note and its index row — no behavioural surface moved.

## Verified

- Counts re-measured against the tree at `7ef346c8` (`git ls-tree -r --name-only 7ef346c8`): total
  3763 and every per-directory count matches the document.
- `7ef346c8` is an ancestor of this branch head (`git merge-base --is-ancestor 7ef346c8 HEAD`),
  so the census pointer the architecture gate requires holds.
- `make check-docs` rc=0 on the pushed head (guard + change-note trio present).
