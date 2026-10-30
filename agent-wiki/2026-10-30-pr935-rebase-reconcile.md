# PR #935 rebase reconciliation

**Issue:** #669 (`agent:implement`) · **Branch:** `fix/669-card-gate-vram` ·
**OpenSpec change:** `card-gate-measured-vram` · **PR:** #935.

## What happened

PR #935 reworks the card gate to read measured evidence instead of the `vram_tier` label. When the
branch was rebased onto the latest `main`, three gates that were structurally fine on the old base
were red on the rebased head:

- **`check-docs` / the architecture census** (`make check-architecture-census`, issue #896): the
  `docs/ARCHITECTURE.md` census named a `measured at` pointer that had been amended away (dangling),
  and its file counts were stale against the rebased tree (1966 stated vs 1993 actual). Root cause:
  the census had not been re-derived after the branch's history was rewritten and the vendored
  store/README moved on `main`.
- **`ci-openspec` / `openspec-tasks-check`** (issue #156): none of the 12 tasks in the
  `card-gate-measured-vram` change were ticked, so the gate red the unchecked checkboxes. Root cause:
  the verified work was never marked done in the change's checklist.
- **`trend-list` AC1** (`tests/test_trend_list_acceptance.py`): the order oracle derived membership
  with the arch-agnostic `fits(m, gb, ram)`, while the product gates by the host's arch (a
  Metal/Apple "unified memory" run is never cuda/rocm/vulkan/cpu evidence, issue #669). On the newer
  vendored store this diverged — a 16 GB cuda host no longer offered a model proven only on M4 Max.
  Root cause: the AC1 expectation did not thread the backend's arch into `fits` the way the product does.

## What the change does

- Re-derives the `docs/ARCHITECTURE.md` census for the rebased tree (1995 tracked files) and moves
  the `measured at` pointer to a real, reachable commit.
- Ticks every verified `card-gate-measured-vram` task so `openspec-tasks-check` is green.
- Makes the AC1 oracle arch-aware (`mp.fits(m, gb, ram, backend)`), matching the product's arch gate.
