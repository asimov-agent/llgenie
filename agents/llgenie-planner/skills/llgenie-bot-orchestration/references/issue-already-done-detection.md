# "Free issue" detection — open + no branch is NOT proof of undone work

Two ways an issue that *looks* free (open, no `agent/issue-<n>-*` branch, no open PR) is already complete. Both wasted a dispatch cycle.

## 1. Merged PR shipped it, but the `closes` keyword never fired

A PR whose body says `closes #N` does not reliably auto-close the issue. GitHub can leave
`closingIssuesReferences: []` and `closedAt: null` while the merge is real. So an open issue +
absent branch reads as "free" even though the content is on `main`.

Before dispatching an issue, run the merged-PR check, not just the open-PR/branch check:

```bash
gh pr list --state merged --search "#<n>" --json number,title,mergeCommit,baseRefName
# and confirm the file at the claimed paths:
git rev-parse origin/main:<path>   # blob unchanged at preflight base AND main => already shipped
```

If the target bytes are already identical in the tree at the preflight base, implementation
produces a **zero-diff PR** — a defect, not a vehicle. The fix is triage (**close the issue as
done**, naming the merged PR), not a new branch. An implementer refusing to open a no-op PR is
the signal working correctly.

## 2. Live profile ahead of tree (live-ahead → tree fold, #791/#1062)

A profile's live skill/reference files can carry content `origin/main` lacks (behaviour grew
before it was versioned). That is real, non-zero-diff work — but distinct from case 1. Detect it:

```bash
# live-only files = present live, absent tree (0 tree-only, N live-only => a fold is owed)
```

Fold only the genuinely live-only files, each byte-identical (sha256 live == tree), one PR.
Never re-fold a file already shipped (that is case 1's zero-diff trap).

## Loop escape

If a lane repeats "already done" with proof, agree once, close the issue, and do NOT re-argue the
same issue a third time. If you were also dispatching a *different* live issue (the fold), point
the lane at that distinct id explicitly and tell it to stop replying on the closed thread — never
re-litigate the closed one to "prove" the open one.
