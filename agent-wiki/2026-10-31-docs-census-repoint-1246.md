# Census re-point: `#1244` pinned the ARCHITECTURE census at a non-existent commit

**Issue:** #1246 · **PR:** this PR (docs/1246-census-repoint-c8817f81) · **measured at** `bb11bb1f`

## Why

`#1244` hand-re-pointed `docs/ARCHITECTURE.md`'s census to `c8817f81`, which is **not a real commit**
(no object, no remote ref, not fetchable). That reddened `make check-docs` on **pure main** (exit 1,
`[census-gate] the doc's pointer c8817f81 is not a real commit` … `no usable referent`), blocking the
`scope`/`check-docs` gate for **every** PR based on `main` — the exact class of `#1236`'s `3104ed11`
regression that `#1222` previously fixed.

The doc's stated counts were also wrong: it claimed tracked=2455 / agent-wiki=329 / docs=337; the
authoritative `measure(bb11bb1f)` is tracked=2458 / agent-wiki=330 / docs=338.

## Change

- Re-point `docs/ARCHITECTURE.md` census at real ancestor `bb11bb1f` and set the counts to the gate's
  own `scripts/check_architecture_census.py measure(bb11bb1f)` (never hand-typed): tracked=2458,
  agent-wiki=330, docs=338, testspp=187, openspec-changes=291.
- `make check-docs` now exits 0 on this head and on a merge-tree onto `bb11bb1f`.

## Acceptance (from #1246)

- [ ] `make check-docs` exits **0** on a clean worktree of this head and on a merge-tree onto `bb11bb1f`.
- [ ] counts equal `measure(bb11bb1f)`, not guesses.
- [ ] `#1236` (generator `architecture_bot.py`) remains the durable recurrence fix; this PR is a
      docs-only short-term re-point and does not touch the generator.
