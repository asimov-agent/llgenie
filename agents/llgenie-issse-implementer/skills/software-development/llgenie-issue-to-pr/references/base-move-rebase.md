# When a rebase is genuinely owed: the `check-pr-base` gate

SKILL.md's step 4 says "rebase only when `mergeable == CONFLICTING`, don't chase main". That is the
default. There is ONE gate-defined trigger that overrides it, and it is the most common reason a
MERGEABLE-but-behind branch still has to be rebased.

## The rule

`check-pr-base` (issue #845) requires

```
git merge-base origin/main HEAD   ==   git rev-parse origin/main
```

so the instant ANY peer PR merges into `main`, `merge-base` falls behind the live tip and the gate
reds against your branch. A green therefore *requires* merge-base==base, and a rebase is genuinely
owed to get there — this is not discretionary chasing, it is the gate's acceptance criterion.

Measure it exactly before touching anything:

```
mb=$(git -C <wt> merge-base origin/main HEAD)
main=$(git -C <wt> rev-parse origin/main)
[ "$mb" = "$main" ] && echo "gate satisfied — NO rebase due" || echo "rebase owed (merge-base != main)"
```

When they are equal, the gate is satisfied even if `gh pr view --json mergeStateStatus` reads
`behind` — do NOT rebase (that is the no-chase rule, and issue #1015 forbids churn). When they
differ, the rebase is the owed work.

## It fires on doc-only peer merges too

A peer merger of `openspec/Dockerfile` + its change-note trio still moves the base sha, so
`check-pr-base` reds even though none of those files overlap yours. The rebase is clean except for
any shared-append file:

- `CHANGES.md` is a RENDERED file. A rebase conflicts because both the peer's row and your row
  append to the same table. Keep BOTH sets of rows in the working tree, then re-render from the
  fragments: `make changes-index` (benedictional). `tests/test_changes_index.py` demands the
  renderer's OUTPUT byte-for-byte — a hand-merged marker set reds it — so never resolve the markers
  by hand and commit; resolve, then render.

## Sequence

1. Confirm merge-base != main (above).
2. `git rebase origin/main`; on a CHANGES.md conflict keep all rows, `git add`, continue.
3. `make changes-index` to re-render CHANGES.md from fragments (do not hand-edit it).
4. Re-run the fast gates at the new head (registry / engine-gap / quant-catalog / strata / agents-line).
5. `git commit --amend --no-edit` when the re-render changed the tree, then confirm merge-base==main again.
6. Force-push with `--force-with-lease` pinned to the OLD remote sha (read it fresh with
   `git ls-remote origin refs/heads/<b>` first), verify LOCAL==ORIGIN==FORK==new head, and re-chase
   CI at the NEW sha — a run at the old head proves nothing and its watcher is now moot.
