# arch-census-referent-membership

Issue: [#1526](https://github.com/asimov-agent/llgenie/issues/1526) — PR: [#1548](https://github.com/asimov-agent/llgenie/pull/1548)

## Why

`docs/ARCHITECTURE.md` §Scripts named `scripts/engine_matrix_pushed.py` as the module answering "did
this run push an engine image" (issue #844). That module no longer exists — removed in `f244efe8`
(2026-10-30, #1029) when the engine-build flow became a producer matrix. It was absent from HEAD and
from the census pin `bb11bb1f`. The parallel sentence in `docs/BOTS.md` named it too. No gate flagged
the stale reference: the census gate counted directory totals at the pinned ancestor sha and never
checked that a LISTED module exists.

## What changed

- **`scripts/check_architecture_census.py`** — added a referent-membership check: every
  `scripts/*.py`/`.sh` name in the §Scripts table (and the parallel BOTS.md push-fact sentence) must
  resolve to a tracked file at the measured sha. Subset check (named ⊆ tree), never equality, so a
  legitimate future addition does not red it. A missing module reddens naming it.
- **`docs/ARCHITECTURE.md`** — dropped the dead `engine_matrix_pushed.py` reference from §Scripts.
- **`docs/BOTS.md`** — corrected the sentence to state the mechanism (the engine-build producer's
  matrix/first-fact check) without the dead file name.
- **Tests** — 3 new tests in `tests/test_architecture_census.py`: a removed module reddens naming it
  (the negative control), a clean table passes, a subset table passes.

## Acceptance (verified)

- `make check-architecture-census` exits 1 naming `engine_matrix_pushed.py` with the stale reference
  present (measured), and exits 0 on the corrected tree.
- `git ls-tree -r --name-only bb11bb1f -- scripts/engine_matrix_pushed.py` is empty (the evidence the
  reference must be corrected, not kept).
- All 9 census tests pass (6 pre-existing + 3 new).
