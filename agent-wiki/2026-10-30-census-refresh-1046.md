# 2026-10-30 — issue #1046: refresh the architecture census after the census gate's first red

## What happened

The `make check-architecture-census` gate (#896) split the drift detection from the refresh on
day one. When it merged (`2856ce55`) it sat on a `main` that had just gained #904 and #1041
un-refreshed, so the merged tree (1978 tracked files, docs 248, agent-wiki 241, openspec 1023,
tests 200, `tests/test_*.py` 170, scripts 119) was ahead of the census #1042 shipped (1966).
That is the gate working — the negative control became the live finding — and the fix is the
refresh this change carries.

## The change

`docs/ARCHITECTURE.md`'s census is re-derived to the tree at this change's head with a `measured at`
pointer to a real commit whose tracked-file count equals `HEAD`. The gate now passes on the refreshed
tree, so `main` stops redding until the tree next grows.

Issue: #1046 (closes), #896
