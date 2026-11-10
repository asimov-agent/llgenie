# Verifying local state before you abandon (or trust a peer's "nothing landed")

## The trap

A degraded local tool channel (empty terminal outputs, "blocked" hints) looks like
"nothing I wrote landed." A peer lane reading `ls-remote` then confirms it from the
remote side: "your branch is not on origin, no worktree exists locally, nothing landed."
Both can be **wrong about the local fact**. Measured in one session: the branch
`fix/...` was not on origin (true) yet a **local** branch with a real commit
(`4da15a6a`) plus an uncommitted edit sat in worktree `llgenie-regnote`, and a second
worktree held the follow-up branch. `origin` being empty proves only that nothing was
*pushed* — never that nothing exists locally.

## The rule

Before you accept "nothing landed," run these three and read the output:

```bash
git branch --list "*<slug>*"                       # a local-only branch?
git worktree list --porcelain | grep -i <slug>      # a worktree the remote can't see?
git -C <worktree> rev-list --count upstream/main..HEAD   # commits ahead of base
git -C <worktree> status --short                    # uncommitted edits
```

- `ls-remote <remote> refs/heads/<b>` empty ⇒ **not pushed**, which is the correct
  outcome when a duplicate is forbidden — but it is not evidence of no local work.
- The commit sha existing locally is worth reporting to the planner so the record is
  accurate, even when the outcome (abandon, do not push) is unchanged. Report the
  discrepancy; do not fight the decision with it.

## What to do with a stale local vehicle

- When a defect is already closed on `main` (verify: `git cat-file -e upstream/main:<path>`
  for each note/file, and quote the merged fix PR), a local branch implementing it is a
  **duplicate vehicle** against the #824 rule. Abandon it: **do not push, do not open a PR.**
- **Do not delete the worktree** — deletion is the owner's call. Report it by name and
  sha, leave it in place.
- Never fabricate a PR to "prove" work; the honest report is that the real fix already
  merged and the local branch is abandoned un-pushed.
