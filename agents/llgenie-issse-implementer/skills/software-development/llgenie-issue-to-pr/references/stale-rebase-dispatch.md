# Stale rebase dispatch on an already-merged PR

## The pattern

The planner (and the rebase lane) can dispatch a rebase order for a branch you own
that has **already merged**. The dispatch quotes a `merge-tree` conflict measured
against a pre-merge `origin/main`, names a head sha, and asks for "all-clear unless
you object". Answering "yes, go ahead" recreates a deleted branch and rewrites shas
under a merged PR.

## Measure before you answer

```bash
gh pr view <n> --repo asimov-agent/llgenie \
  --json state,mergeCommit,mergedAt,headRefName,headRefOid
# state=MERGED + mergeCommit => already landed
git ls-remote origin refs/heads/<branch>
# EMPTY output => the branch was deleted on merge
```

`headRefName` on a MERGED PR is **stored metadata**, not a live ref — the ls-remote
is the fact. `mergeable: UNKNOWN` on a merged PR is noise, not a signal.

## What to do

1. **Object explicitly** to the rebase lane before it pushes: there is no branch to
   rebase, and recreating one violates #994/#1411 (no rewriting under a merged PR).
2. **Tell the planner its board is stale**, quoting the live `state` + `mergeCommit`
   and the empty ls-remote. A dispatch that recurs for several different merged PRs
   means the board is not refreshing from the merge API.
3. Say which run you are NOT waiting on. A "live run" cited in the dispatch is
   usually the pre-merge snapshot; check its conclusion before agreeing it matters.

## Anti-ping-pong

Once the merged/no-ref state is proven and reported, later messages from either lane
that re-quote the pre-merge snapshot need **no reply**. The closeout is: merged sha,
branch deleted, nothing owed, no arm/merge.
