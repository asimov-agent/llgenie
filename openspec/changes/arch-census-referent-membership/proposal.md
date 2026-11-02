# arch-census-referent-membership

## Why

`docs/ARCHITECTURE.md` §Scripts names `scripts/engine_matrix_pushed.py` as the module that answers
"did this run push an engine image" (issue #844). That module no longer exists — it was removed in
`f244efe8` (2026-10-30, #1029) when the engine-build flow became a producer matrix. It is absent from
HEAD and from the census pin `bb11bb1f`. The parallel sentence in `docs/BOTS.md` still names it too.

No gate flags the stale reference. `scripts/check_architecture_census.py` counts `_ls_names("scripts", ref)`
directory totals at the pinned ancestor sha and requires only that the sha be an ancestor of HEAD, so a
REMOVED member of a LISTED group passes every gate. A reader resolving `engine_matrix_pushed.py` finds
nothing, and the next engineer greps the workflow to learn the push-fact gate was folded into
`engine-build.yml`'s producer job — work the prose should have saved them.

## What Changes

1. **Extend `scripts/check_architecture_census.py` with a referent-membership check.** Every
   `scripts/*.py` or `scripts/*.sh` module name that appears inside the §Scripts table (and the
   parallel BOTS.md sentence) must resolve to a tracked file at the measured sha. Use a **subset**
   check (table names ⊆ tree), never equality, so a legitimate future addition does not red it.
2. **Correct the two stale references now.** Drop `engine_matrix_pushed.py` from §Scripts (the
   push-fact gate is now the engine-build producer's matrix/first-fact check, not a standalone
   script), and correct the BOTS.md sentence to state the mechanism without the dead file name.
3. **Prove the gate by its own negative control.** With the stale reference present the new check
   must exit 1 naming `engine_matrix_pushed.py`; after the prose correction it must exit 0 on a
   clean tree.

## Impact

- `scripts/check_architecture_census.py` — adds the referent check.
- `docs/ARCHITECTURE.md` — removes the dead `engine_matrix_pushed.py` reference from §Scripts.
- `docs/BOTS.md` — corrects the sentence that names the dead module.
- `tests/test_architecture_census.py` — adds tests for the referent check (negative control + clean tree).
- `agent-wiki/` + `docs/changes.d/` + `CHANGES.md` — the #1123 change-note trio.

## Out of Scope

This does NOT touch #795 (cross-GROUP edges / grouping-as-data). The referent-membership gap (a named
module that no longer exists) is a different mechanism and lands independently.
