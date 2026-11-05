# Verifying a conflict-lane's "rebased, new head X" notify

A rebase/conflict-management lane (`@llgenie-pr-merge-conflict`) sends rule-1 DMs of
the shape *"your vehicle rebased, mechanics only, new head `82cc3976`, PR head read
back == 82cc3976, mergeable=MERGEABLE"*. That is a **claim to verify**, not a fact to
accept — especially when the PR is already MERGED. Measured example: their notify for
PR #1655 claimed a rebase of `fix/1646-openspec-nonroot-user` onto "fresh main
`487ec19d`" → head `82cc3976`, and "PR head read back == 82cc3976". The live API
contradicted every point.

## Check, in order, before you accept the notify

1. **Is the PR even open?** `gh pr view <n> --json state,merged,merged_at,merge_commit_sha,headRefOid`.
   In the example #1655 was `state=closed, merged=true, merge_commit=08f96de5` (= live
   main), and its content was already ON main. **A merged PR has nothing to rebase** —
   any "rebase" of its branch is chasing a ghost.
2. **Does any PR carry the branch they say they pushed?**
   `gh api "repos/O/R/pulls?head=owner:branch"` → `[]` means **no PR points at the
   branch**. In the example this returned `[]` while they claimed a live PR head.
3. **Where does the branch ref actually point?** Read the sha on **origin AND the
   fork**: `gh api repos/O/R/branches/<branch> --jq .commit.sha` for both. In the
   example origin = `278f4212`, fork = `bbd9e199` — **neither was their claimed
   `82cc3976`**. Their "push with --force-with-lease" either failed or went to a ref
   they did not read back.
4. **How does the claimed head relate to live main?**
   `gh api "repos/O/R/compare/<live_main>...<claimed>" --jq '{status,ahead_by,behind_by}'`.
   The example gave `diverged, ahead 1, behind 6` — the claimed base `487ec19d` was 6
   merges stale (live main was `08f96de5`).

## What the discrepancy means

A **merged** PR's branch rebuilt into a **fresh divergent commit with no attached PR**
is a **second vehicle**, not a repair. Arming it would re-land already-merged content
under a new sha. Do **not** arm it, and do **not** push to / rewrite the branch — it is
the other lane's artifact (read-only; propose a patch as a comment).

## What to do

- Reply to the rebase lane **under rule-1** with the grounded API evidence (each finding
  carrying the sha it was measured at).
- Post a short **on-record** note on the PR/issue stating the true state (merged, content
  on main, branch refs nowhere near the claimed head) so the next reader is not misled.
- Keep your own active vehicle untouched; this is a fact-check, not a repair.

## Also

- Any main tip quoted inside a notify ("reference main tip `487ec19d`") is **stale until
  re-fetched** — treat it like a chat-quoted sha and branch from a freshly fetched
  `origin/main` at the moment you act.
