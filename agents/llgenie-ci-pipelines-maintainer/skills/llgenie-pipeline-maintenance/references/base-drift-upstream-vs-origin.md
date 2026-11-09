# Measure base drift against `upstream/main`, never local `origin/main`

In the `llgenie-main` worktree, `origin` points at the **fork's** `main`
(e.g. `andyholst/llgenie`), which is stale and lags the true tip. The canonical
upstream is `asimov-agent/llgenie`.

## The trap

`git merge-base origin/main <head>` in that worktree compares against the wrong
(older) tip and manufactures a bogus merge-base. A branch that is correctly
rebased onto the live main then looks like it carries "foreign commits" — a
false check-pr-base red.

## The rule

- `git fetch upstream main:refs/remotes/upstream/main`, then compute
  `git merge-base upstream/main <head>` and `git rev-list --count` against
  `upstream/main`.
- Or read the PR's `base.sha` from the API and confirm
  `merge-base(base.sha, head) == base.sha`.
- The authoritative check-pr-base facts are the live PR's `base.sha` and
  `mergeable` fields, never a local ref name.

## Why it matters

A planner or peer lane can quote a `check-pr-base` failure from an *old* head
and an *old* base (e.g. run at head H1, base B1). Before acting, re-measure at
the live head: if `base.sha` already equals the current upstream tip and
merge-base == base, the branch is already rebased and the cited red is a
stale-head artifact — report that, do not re-rebase (rebase is
`llgenie-pr-merge-conflict`'s job, never this lane's).
