# census generator pins a main-reachable ancestor, not the working/PR head (#1236)

The census in `docs/ARCHITECTURE.md` is a claim about ONE commit: the `measured at <sha>`
pointer, and the gate counts the tree AT that commit (`git ls-tree -r --name-only <sha>`). The
generator (`scripts/architecture_bot.py` `surface()`) used to emit the working/PR head as that
pointer — the commit a refresh ran on. When that PR is squashed into `main`, the head sha is
re-authored out of `main`'s first-parent lineage, so the pointer becomes a non-ancestor and the
census gate reds the WHOLE board (`make check-docs` fails on every PR). This happened twice in
one session (`3bba736e` set by #1217's `34ad88f0`, `3104ed11` set by #1224 and orphaned by the
#1229 squash) — manual re-points (#1221→#1222) were undone by the next generation.

## Fix

`surface()` now resolves its pointer to `census_referent()` = `merge-base(origin/main, HEAD)` —
a commit both `main` and the working branch contain, so it survives the squash — and reads the
counts from THAT commit via `git ls-tree -r --name-only <ref>`, never the working tree. A fresh
clone or scratch repo with no `origin/main` falls back to `HEAD`.

The emitted `measured at <sha>` is now always an ancestor of `origin/main` at generation time;
the gate's existing ancestor check stays the backstop. No regression: the census gate still
counts the tree at the stated pointer and still reds a stale number, a dangling sha, or a
non-ancestor pointer.
