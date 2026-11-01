# Rebase discipline and ambient-red routing

Two rebase-related planner failures, and the rules that prevent them.

## Rebase only on CONFLICT

The owner's rule (issue #1015): a lane rebases a PR **only when it is actually `CONFLICTING`** (or its base merged and it must). It does NOT rebase onto every advance of `main`.

- Read `mergeStateStatus`, not vibes. `gh pr view <n> --json state,mergeStateStatus,mergeable,baseRefOid,headRefOid`.
  - `CONFLICTING` → rebase owed.
  - `MERGEABLE` with status `UNSTABLE` (or `BLOCKED`/`BEHIND`) → **NOT a rebase trigger when the red is a check, not a conflict.** `main` advancing under a `MERGEABLE` branch is expected churn; demanding a rebase for it is a planner mis-application of #1015 and burns a bot run for zero merge benefit.
- "Behind main" ≠ "needs rebase". The only reasons to rebase are a real conflict or the base having merged and the branch needing to pick it up.
- Before you demand a rebase, check *why* the branch is not green. If the failing check is not caused by the PR's own files, a rebase will not fix it and the demand is wrong.

### Correct your own wrong demand
When you issued a rebase instruction and the lane pushes back with measured facts + the governing rule, **verify the rule, then retract on the PR thread** — post a correction comment naming the earlier comment id, and re-notify the lane that it holds correctly and owes nothing. A wrong demand left standing teaches the next reader the wrong rule and pressures the lane to fabricate churn. Do not argue down a lane that is right.

## Ambient red belongs to its owning lane
A check red whose failing test points at **another lane's file** (a different seam, a different module) is an *ambient* red for this PR. Do NOT ask the implementer to touch it — that crosses a lane boundary and produces a foreign-file edit in a PR that should not carry it.

1. Root-cause the failing test to the exact file and line (read the run log: `gh run view <id> --log-failed` or the job log).
2. File a **tracked issue** to the lane that owns that file, with concrete acceptance criteria and the failing test + sha.
3. Tell the PR lane explicitly: the red is owned by issue #N in lane X, hold your head, do NOT edit that file, do NOT rebase.
4. The owning lane's fix clears the red; the PR then goes green on its own.

## Verify conclusions, never the merge event
A PR can be merged by the owner *through* a pending or failing deciding leg; the merge event existing does not prove the head was green. When you verify a merged PR, read the head check-run **conclusions** at the merged head sha (`gh run view <id> --json status,conclusion,headSha`), not the merge timestamp.
