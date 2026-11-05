# One-vehicle collapse: don't delete a designated vehicle's branch (issue #1704/+824)

When a double-vehicle arises for one issue, collapse to ONE vehicle by MEASURED MERIT (complete-content fix wins), and collapse by CLOSING the loser — never by deleting the winner's head branch.

- A closed PR whose **fork head branch was deleted** is **terminally unreopenable**: `gh pr reopen` returns 422 "branch has been deleted". The content still lives at the commit sha, but that PR number cannot come back.
- Verify branch existence with `git ls-remote <fork> <branch>` AND `ls-remote origin <branch>` before acting on a stand-down claim — "no implementer branch exists" can be false when a fork branch quietly exists under the same name.
- Zero-mutation of the WINNER's refs: close the loser only. Deleting/rebasing the winner's branch strands the PR and forces content-porting through another lane.
- Never `push --delete` a designated vehicle's branch before its CI concludes.
- If content must be ported, port via review-comment on the surviving vehicle, never a third PR.
