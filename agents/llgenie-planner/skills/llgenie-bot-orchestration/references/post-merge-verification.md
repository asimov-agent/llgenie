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

## When the check-runs read is empty, prove the red from the source

`commits/<sha>/check-runs` can come back empty (quota, retention, or a leg recorded under a
merge-queue ref) even for a merge whose leg genuinely failed. Empty is **not** green — it is
"unmeasured". Do not fall back to the merge event either (an owner merge through a failed leg
leaves `MERGED` in place). Prove the red from the source instead:

```bash
git show origin/main:Makefile | grep -nA3 '<gate-target>'     # which script the leg actually runs
git show origin/main:scripts/<gate>.py | head -40             # what the gate counts/refuses
git show origin/main:<file the PR added> | grep -nE '<the refused shape>'   # the delta itself
```

A set/count ratchet makes attribution mechanical: it refuses when the recorded site-set grows, so
a file the PR added that contributes new sites **is** the red, and naming its `file:line` is the
evidence. This is stronger than a log tail (which proves a leg red without saying whose) and it
costs one `git show` — never run the full containerized suite to prove it. Then file the tracked
issue naming the merge sha, the run id, the gate target, and the offending `file:line`, and hand it
to the lane that introduced the file; a red its own change caused is not a lane-boundary crossing
when that lane is asked to fix it. Expect the lane to retract any "green" it already claimed — a
retraction is the correct behaviour, not a correction to argue with.

## The stacked-PR trap, measured

On one night three PRs reported MERGED while their `baseRefName` was another lane's branch, not `main`:
`#1032` and `#999` merged into `feat/agent-profile-implementer-skill`; `#1045` likewise. **Nothing of theirs was on `main`.** A board that counts them as landed overstates progress, and reverting the base branch would look like a regression on `main` with no cause. Always read `baseRefName` before crediting a merge.

