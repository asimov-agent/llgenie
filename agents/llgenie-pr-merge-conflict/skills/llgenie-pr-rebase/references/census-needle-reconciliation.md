# Census needle reconciliation during a rebase

When a rebased llgenie PR carries a census re-point commit, the rebase can turn the census gate red for a reason a plain conflict check never sees. Reconcile it, do not push a dangling pointer and do not unwind the rebase.

## The contract
`docs/ARCHITECTURE.md` carries a `(measured at <sha>)` needle. `check-architecture-census` requires that sha to be a **real commit and an ancestor of HEAD**. If it is not reachable from HEAD the gate reds with "no usable referent" — the same defect that holds canonical `main` when its own needle names a non-existent object.

## Why a rebase breaks it
A census re-point commit names the fix commit it measured, e.g. `measured at 2c64e3a4`. Rebasing the branch onto a newer `main` renumbers that fix commit (its sha changes, e.g. `2c64e3a4` → `2a1d3fb9`). The re-point commit now points at an **orphaned, unreachable** sha, so `check-architecture-census` reds even though the rebase resolved every textual conflict cleanly. A conflict-only merge-tree check cannot detect this — only running the gate at the rebased head can.

## The fix
Amend the census commit so its needle follows the **renumbered** fix commit:
- Change only the `measured at <sha>` needle in `docs/ARCHITECTURE.md` to the new fix sha.
- Align the commit **subject** too if it quotes the old sha, so message and content agree.
- Keep the original **author**; keep the fix commit's content untouched.
- Re-run `make check-architecture-census` (needle must be an ancestor of HEAD) and full `make check-docs` (rc=0) before pushing.

This preserves the re-point commit's own stated intent ("re-point at the fix commit") rather than shipping a dangling pointer. It is a faithful reconciliation forced by the rebase, not a new behaviour — but **disclose it**: name the orphaned→renumbered sha change in the PR FINISH comment and message the lane that owns the census (ci-pipelines-maintainer / planner), since their conflict-only routing could not anticipate it.

## Checklist
1. `git log --oneline` shows a census re-point commit.
2. Run `make check-architecture-census` at the rebased head — red = orphaned needle.
3. Amend needle (and subject) to the rebased fix sha; keep author.
4. Gate green (`check-architecture-census` + `check-docs` rc=0), needle `git merge-base --is-ancestor <fix> HEAD` = yes.
5. Disclose on the PR and to the census-owning lane before force-push.
