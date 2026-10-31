# Reassigning a frozen lane, and getting the dispatch to land

## A lane that will not start

A lane that freezes on an issue produces the same signature every pass: no branch on the remote, no
claim, no PR, while it acknowledges orders and reports "about to push". Re-sending the same order a
third or fourth time does not move it — the queue is not the constraint.

Procedure:

1. Measure once per pass: `git ls-remote origin "refs/heads/fix/<n>*"` plus `gh pr view <n> --json
   state,headRefOid`. Two consecutive passes with an empty branch list is a frozen lane, not a slow one.
2. Look for a lane that already holds a *verified* copy of the work — a lane whose own comments on the
   issue contain both halves of the diff plus the red-control/passing proofs. A finisher needs the
   diff, not the authorship.
3. Post the reassignment on the issue thread (who is relieved, who takes the finisher role, why) and
   send the relieved lane an explicit "do not touch this issue" line in the same dispatch, so the two
   cannot race onto one vehicle.
4. Give the finisher the mechanical steps only: branch name, rebase onto the freshly fetched `main`
   sha, "one ready-for-review PR closing #<n>", and the two things to report back (pushed sha + PR
   number). Never re-derive the technical content — it already proved it.
5. Do not reassign work whose only copy is an uncommitted worktree (a crashed worker's tree, a
   commit that exists only on that host's clone). Say so instead: that commit is not extractable by
   any other lane, so the constraint is the host, not the dispatch.

A reassignment lands in minutes when the finisher already holds the diff — that is the measurement
that tells you the frozen lane was the problem and the task was never the problem.

## Verifying a finisher PR in one API block

Accept a finisher report only against one block that answers everything at once:

```bash
gh pr view <n> --json state,isDraft,baseRefName,headRefOid,mergeStateStatus,body   # OPEN, non-draft, base main, closes #<issue>
gh pr view <n> --json autoMergeRequest --jq '.autoMergeRequest'                      # armed != "gh pr merge --auto exited 0"
git ls-remote origin refs/heads/<branch>                                            # the sha the lane claims is really pushed
git diff --stat origin/main...origin/<branch>                                       # diff scope == the promised files
git merge-base --is-ancestor origin/main origin/<branch>                            # rebased, not stale
```

Then confirm the promised *behaviour* exists in the pushed blob, not in the lane's description:
`git show origin/<branch>:<path> | grep -B2 '<symbol>'`. A marker/guard the lane says it added is
only real when it is in the tree the remote serves.

## Getting a DM to a peer bot at all

- `status=failed` is a hard non-delivery — the peer never saw it. Retry is correct and idempotent
  when the instruction is "do these steps to this one branch".
- `queued` / "remains pending or its outcome is unknown" is NOT a failure. Retrying one of these
  duplicates the instruction; the gateway retains receipt. Leave it.
- "Durably queued for the live Bot Chat owner" is success — stop there.
- Two hard failures in a row usually mean the peer's session is mid context-compression and cannot
  accept a turn. Wait in the foreground (`sleep 150; date -u +%H:%M:%SZ`) and retry exactly once;
  that third attempt queues durably. Do not loop retries back-to-back.

## Exact-match census pins vs. the PR that changes the set

When a pin asserts `set(actual) == EXPECTED` over a registry (network markers, roster, manifest), a
PR that legitimately adds entries to that set reds the pin — by design. The fix belongs in the *same
branch and vehicle*: extend the expected census with the names the PR added, push to the existing
branch, re-read the arm. A second PR for the census is the two-vehicle mistake.

Read the assertion diff before triaging: `actual - expected` naming exactly the entries the PR
introduced means the PR is correct and the census is stale. Entries in `expected - actual` mean the
lane dropped coverage it did not intend to drop — that one is a real defect.
