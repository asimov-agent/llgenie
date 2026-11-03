# census gate: shallow/filtered checkouts are not doc defects (#1686)

`scripts/check_architecture_census.py` no longer renders a **shallow-or-filtered checkout** as a
document defect. A worktree cloned off a shallow primary (or a `--filter` clone) holds the tip but
not a far-back `measured at <sha>` pointer object, so `git cat-file -e <sha>^{commit}` and
`git merge-base --is-ancestor <sha> HEAD` both returned non-zero and the gate exited 1 "not a real
commit / not an ancestor / no usable referent" — turning an environment-depth failure into a false
doc-defect red that sent lanes chasing phantom pins.

The gate now distinguishes the two (mirroring the #1141 `git_unreadable()` exit-2 contract):
- `pointer_is_unfetched()` probes whether the checkout is shallow (`git rev-parse
  --is-shallow-repository`) or the pointer is still an ancestor of the remote-tracking
  `origin/main`/`origin/HEAD`. If so, the object is real but merely unfetched, and `check()` exits 2
  with a **CHECKOUT-DEPTH** diagnostic naming the missing object and the remedy
  (fetch/unshallow) — the document is not at fault.
- When the pointer is provably absent from `origin/main` too (a full clone), the gate still reds as a
  doc defect (exit 1), preserving the #1221/#1246/#1236 pin protection.

Covered by two new tests driving the gate through a **real** `--depth 1` clone:
`test_a_shallow_checkout_with_an_unfetched_pointer_is_depth_not_a_doc_defect` (exit 2, CHECKOUT-DEPTH)
and `test_a_genuinely_foreign_or_dangling_pointer_still_reds` (exit 1, no regression). Docstrings at
the top of the script and in `docs/ARCHITECTURE.md` §Structural gates state the exit-2 checkout-depth
case alongside the existing unreadable case.
