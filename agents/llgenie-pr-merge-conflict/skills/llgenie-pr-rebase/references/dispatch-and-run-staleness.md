# Dispatch and run staleness

## A dispatched head sha is stale by the time you read it

A planner, reviewer, or another lane hands you "rebase head X (cut from Y) onto current main." That measurement predates your read; the branch may already have moved — and the dispatch's branch/head-repo identity can be wrong too (a "fork-profile agent-ish" dispatch pointing at a canonical `docs/...` branch is itself a sign the measurement is old). Before any rebase:

- `git fetch` explicitly for both `main` and the PR branch (e.g. `+refs/heads/main:refs/remotes/origin/main +refs/heads/<branch>:refs/remotes/origin/<tag>`), then `git merge-base --is-ancestor origin/main <live-head>` and `git rev-list --count origin/main..<live-head>`.
- Read the live head from the wire (`gh api repos/.../pulls/<n> --jq .head.sha`, `.head.repo.full_name`, `.mergeable`) — never trust the sha quoted in the dispatch text.
- If `merge-base == origin/main` (head already cut from current main, one commit ahead, no foreign commits), the rebase is already done. **Report-and-stop**: post the ancestry proof on the PR, tell the dispatcher their sha was stale, and push nothing. Re-touching a branch another lane already rebased is double-work and a force-push collision (one-pusher / last-pusher-owns-head).

## A quoted sha that RESOLVES in the object DB is not necessarily the wire head

The stale-dispatch check above can pass while the dispatch is still wrong, because **a sha that
`git cat-file -t` reports as a `commit` may be a purely LOCAL object — an earlier cut that was never
pushed** (or was superseded by a later push). It resolves, it has a plausible subject and author, and
it is still not the branch.

Measured: a dispatch said "your push moved the head `f9b5529b → d5534496`; rebase it onto the tip,
it is still DIRTY on `CHANGES.md`." `git cat-file -t d5534496` → `commit`, parent `ea8c239e`, subject
matching the PR — everything looked right. But `git ls-remote origin refs/heads/<branch>` returned a
**different** sha (`fd204b4c`, cut from current `origin/main`, ancestry exit 0 = CURRENT, `merge-tree`
rc=0 clean). `d5534496` was a leftover local cut of the maintainer's earlier worktree, never on the
wire, not an ancestor of the live head. Following the dispatch would have force-pushed a stale branch
back over a correct one — the exact "freshly-stale" churn the batch-vs-single-PR cadence argument is
about.

So existence is NOT identity. The pre-flight order is:

```bash
git ls-remote origin refs/heads/<branch>            # the WIRE head — authoritative
git fetch origin '+refs/heads/<branch>:refs/remotes/<tag>'   # then re-read it locally
gh pr view <n> --json headRefOid                    # the PR's own head, cross-check
git merge-base --is-ancestor origin/main <tag>      # exit 0 → CURRENT
```

When the quoted sha ≠ `ls-remote`/`headRefOid`, say so plainly ("`<quoted>` is a local object, not the
wire head; the live head is `<new>`, already current") rather than either obeying the dispatch or
silently ignoring it. Verify the quoted sha against the wire *before* you run `git cat-file -t` on it —
a resolvable object proves the fetch happened, not that a push did.

## Report the ANCESTRY PROOF, not a bare sha — a head whose main is not an ancestor is not rebased

The deliverable of a rebase (or of a "already done" hand-back) is the ancestry line, not the sha alone:

```
git merge-base --is-ancestor origin/main <head>  → exit 0 → CURRENT
```

A head can have a clean `merge-tree`, the right subject, and the right diff against a *literal* copied
sha and still be cut from a three-commits-old main — the diff looks right while the base is wrong. State
`CURRENT` (the exit-0 line) alongside the sha in every finish bookend; a reader who gets only the sha
cannot tell whether the rebase actually happened or just moved the ref.

## The live head can carry MORE work than the sha you were given — rebase the LIVE head

The dangerous variant of a stale dispatch sha is not "already rebased", it is **"the live head is a
generation ahead and carries work the quoted sha lacks."** Replaying the quoted sha then silently
deletes whatever landed after it.

Measured: a dispatch said "head `f9b5529b`". The live wire head was a different commit — a repair lane
had pushed its own fix at that head, adding ~16 lines to the main script and ~69 to its tests plus two
new files. Rebasing `f9b5529b` would have produced a clean, green, *smaller* branch and dropped the
repair. Nothing would have flagged it: `check-pr-base` and the guard chain all pass on the truncated
tree.

So the pre-flight is a **content** comparison, not just an ancestry one:

```bash
# what does the live head have that the quoted sha does not?
git diff --stat <quoted-sha> <live-head>
# and: is the quoted sha even an ancestor of the live head?
git merge-base --is-ancestor <quoted-sha> <live-head> && echo quoted-is-an-ancestor || echo diverged
```

Rebase **`<live-head>`**, and say in the finish comment which sha you actually replayed and why the
dispatched one was not it. When the live head is *behind* the quoted sha the same check tells you the
dispatch is simply old; when it is *diverged*, stop and report rather than picking a side.

## The dispatched CONFLICTING/DIRTY premise can also be false

A dispatch often asserts `mergeable=CONFLICTING`, `mergeStateStatus=DIRTY`, "zero CI checks ran".
Re-measure all three before choosing a resolution strategy. Measured: a dispatch ordered a
`CHANGES.md` union on a PR that was in fact `MERGEABLE` with `merge-tree` rc=0 — the rebase resolved
with **no conflict at all** because main's regenerated index already agreed. Had the instruction been
followed literally (hand-merge both index rows) it would have *introduced* a conflict into a clean
rebase. Report the corrected premise in the finish comment; the dispatcher's concern is still valid,
only its measurement was old.

## A claim whose own run has concluded is a DEAD hold, not a live one

A `bot-claim: … ttl=240m run=<id>` comment reads as a live hold for its whole TTL, but liveness comes
from the **run's status**, not the marker's timer. Check `gh run view <id> --json status,conclusion`:
`completed` means the claiming lane is done and the branch is free to rebase, however fresh the comment
looks. Rebasing under a genuinely `in_progress` claim is the collision to avoid; waiting out a TTL on a
concluded run just burns hours.

## A failing check bound to the head can be a pre-body-edit snapshot

A PR body edit (AGENTS/BASE/SYNC lines, a fix comment) fires no CI run. A guard or body-gate job red at the head may have been measured against the body as it stood BEFORE the edit. Before diagnosing a code/base defect:

- Read the live body (`gh api repos/.../pulls/<n> --jq .body`) and confirm the lines the gate wants are actually present now.
- Map the failing check to its run/job/step (`gh api repos/.../commits/<sha>/check-runs` → `gh api repos/.../actions/jobs/<job-id> --jq '.steps[]|select(.conclusion=="failure")'`), then `gh run rerun <run-id> --failed` to re-read the current body. The remedy is a rerun, not a code change, when the body already satisfies the gate.
- A guard aggregate can show one `failure` next to several `success` (multiple guard jobs); name the specific failing step, never the aggregate.

## An `in_progress` run at the head is not automatically a blocker — check BOTH its workflow's `cancel-in-progress` and its `updatedAt`

The fleet rule is "never push while a run at the head is in progress", because a push cancels it. That
ban applies to runs the push can actually cancel. Two reads decide, in this order:

1. **Does the workflow cancel on new pushes?** `grep -A3 '^concurrency:' .github/workflows/<w>.yml`.
   `cancel-in-progress: false` (typical for a trigger/dispatch workflow that joins a producer queue)
   means a force-push creates a NEW run and leaves the old one alone — pushing harms nothing.
2. **Is the run live or a zombie-wait?** Compare `gh run view <id> --json updatedAt` against now and
   against its own dispatched producer's conclusion. A run whose `updatedAt` is hours old while a
   producer it awaits already concluded is a zombie — the job will never progress and GitHub simply has
   not closed the row. Report the staleness (`updatedAt` vs now) as the evidence, never just
   "in_progress, so blocked".

Both reads together are the decision; either alone mis-classifies. A genuinely live run on a
cancelling workflow is a real wait — finish the matrix, do not cancel it to free a slot.
