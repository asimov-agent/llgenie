# Board state, holds, and post-merge truth

Everything in this file is about the difference between what the board *says* and what the
tree *is*. The board (labels, `mergeStateStatus`, comment threads, delivery notifications) is
advice; `origin/main` at a sha is the fact.

## 1. A hold label is advice, not a gate

`do-not-merge` is a comment-shaped signal read by humans and by whichever workflow happens to
look for it. It cannot stop a merge performed by someone with push rights, and it does not
alter `mergeStateStatus` — a held PR reads exactly like an abandoned one.

- Placing a hold is **not** a control. It buys a reviewer's attention, nothing else. Never
  report "the merge is blocked" on the strength of the label; report "the hold is placed and
  the PR is still open at `<sha>`" and re-measure next pass.
- Always pair a hold with a **tracked removal condition**: the issue that will make the tag
  removable, named in the same comment, with the label removed by you when that issue's
  evidence lands.
- Measure the hold and the merge in the **same pass, within seconds**: `gh pr view <n> --json
  state,mergedAt,mergedBy,labels,headRefOid`. A PR can go from "held" to `MERGED` between two
  of your own tool calls. If it did, the hold is now historical, not operative.
- One concurrent actor with push rights voids every hold you place this hour. Sequence holds
  **before** the last green leg lands, or do not bother: a hold placed while checks are
  already green is a coin flip.

## 2. Post-merge verification is the only real gate

Once a PR merges, its diff **is** main's. The verdict that matters is measured on the merge
result, not on the PR head:

```bash
gh pr view <n> --json state,mergedAt,mergeCommit,baseRefName,headRefOid,labels
# baseRefName must be the default branch — a stacked PR "merged" into a parent branch did not land
# measure the acceptance criterion ON MAIN, at the merge tip, from a clean worktree:
git fetch origin main && git -C <clean-worktree> checkout <mergeCommit>   # or origin/main if it is the tip
<run the acceptance gate at that sha>                                      # quote the run id / rc
```

- Re-run the gate at the **merge tip**, not at the PR's head sha — the merge commit is what
  main now contains, and a squash can produce a different tree than either parent.
- If a criterion fails on main: file a **new** issue naming the merged PR, the merge sha, the
  failing gate and its run id; delegate it to the owning lane; post the finding as a comment on
  the merged PR so the next reader finds it where the work lives.
- **Never reopen a merged PR.** Its review is over; the diff is main's. Reopening produces a
  resurrected branch that conflicts with the tree it forgot it became.
- The post-merge finding is usually "the fold was measured against a base the fold itself
  changed" — re-reduce the acceptance set at the new head instead of carrying it over.

## 3. Routing: one dispatch comment, and reconcile supersessions out loud

Two planner comments routing one issue to two different lanes is a defect **you** created, and
it is worse than a wrong route: the lane that reads second sees the other lane's brief as a
claim and stands off, so the issue idles while both lanes believe it is owned.

- **One issue, one current routing comment.** When the route changes (wrong lane, wrong
  sequence, a gate that opened or closed), post a single reconciliation that (a) names the
  comment id it supersedes, (b) states the owning lane as a decision, (c) states the frozen
  premise that changed ("the wait on X is over: X merged at `<sha>`"), and (d) says who is now
  off the issue.
- Pick the lane by **what the change touches**, not by the issue's label:
  - content-only commit of a file already under `agents/<profile>/` (skill text, a reference the
    gate wants in-tree) → the documentation lane;
  - a gate, script, workflow, test or acceptance-criterion change → the implementer lane;
  - an ordering question spanning two vehicles → you decide it and post the order, never "either
    lane first".
- The newest comment alone is **not** the routing. Nothing in the GitHub UI marks a comment
  superseded, so a lane reading top-down acts on the old brief. Name the superseded id.
- Re-read the whole comment thread before dispatching on an issue you have touched before; a
  second routing comment may already be there and it may be your own.

## 4. Verifying your own post: match markers, not markup

You must be able to prove a comment landed **by id**, and a false "verified" is worse than a
failed post. Two traps, both real:

- **Markup-dependent regex gives false negatives.** A body renders text inside code spans as
  literal backticks, so a check for a spelled-out number fails while the digit sits inside
  `` `...` ``; and headers in some repo conventions are single-`#`, so a `test("## Problem")`
  check fails on a perfectly shaped body. Verify with substrings that do not depend on
  formatting (`"planner rows"`, `"Problem"`, `"\\#<id>"`), or strip backticks from both sides
  before comparing.
- **A jq filter that returns `false` is not proof the post failed.** Re-read the raw body,
  decide whether the marker exists in another form, and only then correct the ledger. Never
  record "verified" for a check you did not resolve, and never re-post to "fix" a verification
  failure — duplicates on a thread are worse than a wrong jq filter.
- Post and verify in **separate calls**: the POST response id is the only handle you have, and
  re-posting after a tool error creates the duplicate the guard was trying to prevent.

## 4b. Editing an issue body: the anchor must be the literal line, and a miss is not a failure

When you PATCH an issue body to correct a stale value (an md5 anchor, a scope line, a superseded
premise), the `old_string` is matched **literally**, markup included. Two rules that save a loop:

- **Grep the body for the token first, then copy the literal line.** A body line reads
  `- \`file.md\` — md5 \`<hash>\`, 58 lines, 3,561 B`; an anchor reconstructed as
  `file.md, 58 lines, 3,561 B` (no bullet, no backticks, no em-dash) never matches. Get the exact
  text with `gh issue view <n> --json body --jq '.body' | grep -n '<token>'` and use it verbatim.
- **A miss after an earlier success is the patch having landed, not a failed patch.** PATCH is not
  idempotent: once the first run replaced the anchor, every re-run reports `ANCHOR-NOT-FOUND`
  because the precondition is gone. Before concluding failure, read the body back and look for the
  **new** value; only treat it as a real miss if the old value is still there. Write the helper so
  it prints the matching lines on a miss — that output is what tells you which of the two cases you
  are in.
- **Make the correction script state-asserting, not blind.** Assert `old in body` and print the
  post-PATCH read-back (`old present? new present?`) so one call proves the mutation instead of
  leaving you to guess from an exit code.

## 5. Delivery notifications are lagging echoes

Background-process completion notices (`proc_*`, queued DM deliveries) carry the facts that were
current when the *job* was built, not when it fired. A notice can restate a main sha, a PR head
or a branch state that your own measurements have since superseded.

- Treat any notification whose body quotes a sha as **a pointer to re-measure**, never as news.
- Re-measure main/PR/run state before acting on a notification; if the facts moved, say so and
  propagate the correction to the lane that is about to act on the stale premise.
