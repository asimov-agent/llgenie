# Verifying a rebase claim: snapshot vs verdict

A lane reports a rebase with a new head sha and "push done / MERGEABLE". Two failures are common
and both are settled by the same discipline: re-measure, then walk the chain.

## 1. One read is a snapshot, not a verdict

A lane whose terminal relay exercises mid-push can deliver the write seconds later. A PR head
still showing the pre-push sha — or `gh api repos/<o>/<r>/commits/<sha>` answering 422
`No commit found` — proves *not yet*, never *never*. Re-query `headRefOid` a few seconds later
before telling a lane its work did not land. Two reads apart separate the two cases cleanly:

```bash
gh pr view <n> --json headRefOid --jq .headRefOid          # read 1
# ... a beat later ...
gh pr view <n> --json headRefOid --jq .headRefOid          # read 2 — moved = push landed
```

Also measure the *branch* tip, not just the PR's cached head: `gh pr view <n> --json headRefName`
then compare. A head that moved between your own two calls is a successful push, and the lane's
report was true at delivery even though your first check disagreed.

## 2. Trust the chain, not the claimed sha

Never accept "rebased onto <main-sha>" from the report. Walk the parent chain from the head back
to the named base and count the hops:

```bash
cur=$(gh pr view <n> --json headRefOid --jq .headRefOid)
for i in 1 2 3 4 5; do
  p=$(gh api repos/<o>/<r>/commits/$cur --jq '.parents[0].sha')
  echo "depth$i $cur -> $p"
  [ "$p" = "<named-base-sha>" ] && { echo "base confirmed at depth $i"; break; }
  cur=$p
done
```

- The base appearing at depth _N_ proves the rebase is onto that exact commit; the hop count is
the number of replayed commits, which should match the lane's "N commits replayed" claim.
- A **different base** (e.g. an old local ref the lane fetched from its clone instead of the
  canonical remote) appearing instead of the named one is the stray-shadow failure: the branch
  was built on a stale commit and is not mergeable against real main. Route a re-rebase.
- Checking `headRefOid` alone cannot see this; only the chain can.

## 3. Read the state transition

`mergeStateStatus` is the outcome: `DIRTY`/`CONFLICTING` before a correct rebase, `BLOCKED`
after (clean merge, merely awaiting the review gate — see the REVIEW_REQUIRED note in SKILL.md).
A head that changed while the status stayed `DIRTY` means the push landed onto the wrong base or
against a base that has since moved again — go back to step 2.

Corroborate local gate output with registered runs, not with the lane's quote of its own rc:

```bash
gh api "repos/<o>/<r>/actions/runs?head_sha=<new-head>&per_page=8" \
  --jq '.workflow_runs[] | "\(.name) \(.status)/\(.conclusion // \"-\") \(.id)"'
```

Runs at the *new* head prove CI actually saw the pushed commit; a lane's `make` exit code is not
evidence unless a run exists at that sha.

## 4. Close the bookend, don't re-verify twice

When the push is confirmed, reply with the measured facts (full sha, chain depth, run ids) and
ask only for the missing FINISH bookend. Do not ask the lane to re-quote gate rc it already
reported — the registered runs are the evidence and a second verification round is pure ping-pong.
