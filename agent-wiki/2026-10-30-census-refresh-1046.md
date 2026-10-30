# 2026-10-30 — issue #1046: refresh the architecture census after the census gate's first red

## What happened

The `make check-architecture-census` gate (#896) split the drift detection from the refresh on
day one. When it merged (`2856ce55`) it sat on a `main` that had just gained #904 and #1041
un-refreshed, so the merged tree (1988 tracked files, docs 250, agent-wiki 243, openspec 1027,
tests 201, `tests/test_*.py` 171, scripts 120) was ahead of the census #1042 shipped (1966).
That is the gate working — the negative control became the live finding — and the fix is the
refresh this change carries.

## The change

`docs/ARCHITECTURE.md`'s census is counted once more, this time under the tree-at-named-sha
contract the gate took in #1053/#1055: the numbers are read from `git ls-tree -r
--name-only 564e9383` — 2009 tracked files, `docs/` 253, `agent-wiki/` 246, `openspec/`
1038, `tests/` 203, `tests/test_*.py` 173, `scripts/` 121 (266 changes) — and the
`measured at` pointer names that commit. It is an ancestor of the branch head and of
`origin/main`, so the census is reproducible from a tree this branch contains and no longer
has to name a PR head, which dangled after the squash. The five stacked census sentences
earlier re-derives had left in the block (one per rebased pointer, `35d22ea`…`9508bb0`) are
collapsed to one.

Issue: #1046 (closes), #896, #1053, #1055
