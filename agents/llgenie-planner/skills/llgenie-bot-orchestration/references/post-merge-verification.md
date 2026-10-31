# Post-merge verification: a merge is not a completion

**Every merged PR must be re-verified after the merge.** A green pre-merge PR proves the branch passed the gates **at that head on that base**. It does not prove:

- the squashed result on `main` is green (a squash can drop a trailing commit; a merge can collide with another PR merged minutes earlier),
- the issue's acceptance criteria are actually met on `main` (a stacked PR "merges" into its parent branch, not into `main`, so nothing reaches `main` at all),
- the change did what it claimed once combined with everyone else's.

## The pass (run it for every merge, oldest first)

```bash
# 1. what merged, and into WHAT (base matters more than state)
gh pr list --state merged --limit 20 --json number,title,mergedAt,mergeCommit,baseRefName
#   baseRefName != main  ⇒ it merged into a parent branch; its content reaches main only when THAT merges

# 2. is main itself green at the resulting tip?
M=$(gh api repos/<o>/<r>/commits/main --jq .sha)
gh api repos/<o>/<r>/commits/$M/check-runs --jq '[.check_runs[]|{n:.name,c:(.conclusion//.status)}]|group_by(.c)|.[]|"\(.[0].c): \([.[].n]|join(", "))"'
#   any in_progress ⇒ acceptance is UNVERIFIED, not verified. Say so and re-check.

# 3. do the issue's acceptance criteria hold on main?
#   read the issue, then measure each criterion on main — not on the PR head
```

## Failure handling

If main is red at the merge tip, or a criterion does not hold:

1. **File a new issue** (do not reopen the merged PR — its history is closed and its diff is now `main`'s).
2. Name the merged PR, its merge commit sha, the exact gate/criterion that fails, and the run id proving it.
3. **Delegate** it to the lane that owns that surface, with the acceptance condition spelled out.
4. If `main` is red, that is the highest priority on the board — every open PR inherits a broken base.

## The stacked-PR trap, measured

On one night three PRs reported MERGED while their `baseRefName` was another lane's branch, not `main`:
`#1032` and `#999` merged into `feat/agent-profile-implementer-skill`; `#1045` likewise. **Nothing of theirs was on `main`.** A board that counts them as landed overstates progress, and reverting the base branch would look like a regression on `main` with no cause. Always read `baseRefName` before crediting a merge.

