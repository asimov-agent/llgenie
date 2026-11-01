# Main-branch CI and `cancel-in-progress`

**Rule:** measure main CI at the **true tip** only. A burst of merges produces a chain of `cancelled` runs on `main`; only the newest run at the final tip decides green or red.

**Why:** `main`'s CI workflow uses `concurrency: cancel-in-progress: true`. Each consecutive merge push cancels the previous run. So after the owner approves a rapid batch (#1093, #1191, #1199, #1200, #1201 in one window) the run list at `main` shows a row of `completed / cancelled` runs — one per merge, all of which were superseded, not failed. Flagging those as a red `main` is a false alarm; the deciding run is the one whose `headSha` equals the current tip.

**How to measure:**

```bash
cd <repo> && git fetch origin main && TIP=$(git rev-parse origin/main)
gh run list -R <owner>/<repo> --branch main --workflow CI \
  --json databaseId,status,conclusion,headSha \
  --jq ".[]|select(.headSha|startswith(\"${TIP:0:8}\"))|\"\(.databaseId) \(.status)/\(.conclusion)\""
```

- `in_progress` is **not** green — say "deciding run pending", never upgrade to green.
- `completed / cancelled` at a tip with a **newer** tip existing means a newer merge superseded it; re-measure at the new tip.
- `completed / cancelled` at the **current** tip with no newer commit is the actual signal — investigate that one.

**Do not** re-run or cancel anything to "clear" cancelled rows; they are evidence of the queue working, and cancelling a live run to tidy the board is forbidden.

**Paired pitfall:** `gh pr checks` reports a `fail` column entry for `cancelled` jobs on PRs as well; a PR whose checks are all green can still read `BLOCKED` on `REVIEW_REQUIRED` (the #1088 wall — every lane PR is authored with the owner token, so no lane can self-approve). Green is never the same as mergeable.
