# "Green, awaiting owner merge" vs already merged

A lane's claim that a PR is "green at <head> awaiting owner merge" is frequently stale — the PR may already have merged. Squash merges make this look pending: the branch head is **not** an ancestor of `main`, so `git merge-base --is-ancestor <head> origin/main` returns NO for perfectly merged work.

Settle it from the PR object, never from the branch ref:

```bash
gh pr view <n> --repo asimov-agent/llgenie --json state,mergedAt,mergedBy,mergeCommit \
  --jq '{state,mergedAt,by:.mergedBy.login,merge:.mergeCommit.oid}'
```

- `state=MERGED` + a `mergeCommit.oid` means done. Confirm with `git merge-base --is-ancestor <mergeCommit.oid> origin/main` → YES (the squash commit is on main; the branch head is not, and that is expected).
- Only `state=OPEN` with ms=BLOCKED/REVIEW_REQUIRED and no `mergedAt` is genuinely awaiting the owner gate.

When a lane reports a merged PR as pending, correct the stale reading (name the sha that proves it merged) instead of re-dispatching or replacing the lane on work already on `main`. Report the merge-commit sha, not the head sha, as the merged-state fact.

**Note:** SKILL.md and references/verifying-lane-claims.md are at the 100 KB cap, so this file is not yet linked from the pointer list — fold it into `verifying-lane-claims.md` after that file is trimmed.
