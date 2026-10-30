# The census gate refers to the tree at the named sha, not HEAD

`scripts/check_architecture_census.py check()` counted `git ls-tree … HEAD` and compared the
`measured at` pointer's tree count against HEAD. That made the census a fact about HEAD, so every PR
that added or removed a file had to rewrite the same `docs/ARCHITECTURE.md` block — the one shared doc
became a conflict point on every open PR — and the pointer it was forced to write named the PR's own
head, which the squash-merge then orphaned (the #1048 → #1051 → #1052 red chain on main).

The gate now treats the census as a fact about **the tree at the sha the document names**:

- counts are checked against `git ls-tree -r --name-only <named-sha>`, so a PR that adds files but
  leaves the doc untouched passes (its doc names a `main` sha whose tree the numbers describe);
- the pointer must be a **real commit AND an ancestor of `HEAD`** (`git merge-base --is-ancestor`) —
  a pointer to an unmerged branch head, or to any sha with the right file count, reds before it can
  dangle after a squash-merge;
- the stale-census teeth are kept: doc numbers that disagree with the tree at the pointer's sha still
  red, on `main` and in PRs alike.

Refreshing the census is now a single docs change on `main` (#1046/#1047), never per-PR churn. The
contract test (`tests/test_architecture_census.py`) drives the real `check()` against a throwaway repo:
file-adding branch passes, a stale count reds, a non-ancestor pointer reds naming the sha, a missing
pointer reds naming `docs/ARCHITECTURE.md`.