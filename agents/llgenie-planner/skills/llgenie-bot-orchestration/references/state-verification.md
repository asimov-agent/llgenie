# Verifying state before reporting or acting

Every instrument in this stack reports something adjacent to the truth. These are the checks that decide
whether a claim is evidence.

## Read the failure text, do not infer it

```
gh api repos/<o>/<r>/actions/jobs/<id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g'
```

- Without `--allow-escape-sequences`, `gh` prints "the response contains terminal escape sequences" and the
  log looks empty. That is a client guard, **not** an API limitation — treating it as "logs unavailable" turns
  a one-command diagnosis into hours of guessing.
- `gh run view --log-failed` refuses while the **run** is in flight, even when the **job** has completed.
- A blank log is evidence of nothing. Quote the failing test ids and the reproducing command, or say the
  cause is unknown.

## `run.status` and `mergeStateStatus` both lie politely

- `run.status` can read `queued` for an hour while jobs hold runners and one step is stuck. An alarm keyed on
  it sleeps through a hang. Read **job-level** state (`status`, `started_at`, `runner_name`, step transitions).
- A job with no `timeout-minutes` inherits a very long platform default, so "hung" and "slow" are
  indistinguishable for hours. Give every job a ceiling above the slowest job it calls, and test the
  caller/callee relation in both directions.
- `mergeStateStatus`: `UNSTABLE` occurs with **zero failures** (pending checks are enough), and `BLOCKED` is
  what a required-review rule produces on every PR whether or not checks fail. Neither distinguishes
  advisory from effective. Snapshot `statusCheckRollup` conclusion counts (including the no-conclusion
  count), `reviewDecision`, `isDraft` and the auto-merge decision together.
- Decoder for a PR: `MERGEABLE` + `BLOCKED` means waiting on checks/approval — **only `CONFLICTING`/`DIRTY`
  means rebase**. Rebasing on `BLOCKED` restarts a long matrix to change nothing.

## Terms that are not verdicts

- `cancelled` is never a pass. A run's verdict is its completed conclusion plus named cancelled rows.
- A queued run owes no verdict, so superseding it destroys nothing; superseding a **running** one destroys the
  verdict it was earning. That distinction is the whole reason "never push while a run is at the head" is a
  rule and not a preference.
- A head with only `cancelled` runs has **no verdict**, not a red one.

## Every finding carries a sha AND a ref

A log is evidence about **the ref it ran on**. Quoting a branch log as a `main` fact turns a PR defect into a
repo defect. State `main@<sha>`, or `branch@<sha>`, and re-read both in the turn you report them — a cached
`main` sha from an earlier message is the most common stale claim in a long session.

```
git fetch <upstream> main && git rev-parse --short <upstream>/main
gh pr view <n> --json mergeable,mergeStateStatus,headRefOid,baseRefId
```

## Prove a push landed before reporting it

`git push` exiting 0 is not proof the remote moved — a lease mismatch, a hook, or a wrong ref prints
plausible output. Read three refs back and require all three equal:

```bash
git push -q origin HEAD:refs/heads/<b>
echo "local=$(git rev-parse --short HEAD) remote=$(git ls-remote origin refs/heads/<b> | cut -c1-8)"
gh pr view <n> --json headRefOid --jq '.headRefOid[0:8]'
```

**`mergeable` reads `UNKNOWN` immediately after a large push.** GitHub recomputes the merge base
asynchronously; poll it again (a few seconds) until it settles to `MERGEABLE` or `CONFLICTING`. Reporting
`UNKNOWN` as "conflicted" or "can't merge" is a measurement taken mid-recompute, not a verdict.

## "Diff is non-empty" is not evidence of unique work

An older base guarantees a non-empty tree diff. To decide whether a worktree holds unpublished work, test
**per-file blob equality against three sources**: the upstream branch, the target PR's remote, and the
branch's own remote. Anything matching none of them is worth reporting; anything matching one is older.

Corollary: **a local branch sitting at the base commit plus a published PR is a repurposed checkout, not data
loss.** Before concluding something was deleted: `git ls-remote`, `git ls-tree -r`, the PR's file list, and
blob sizes via `git cat-file -s`.

## A sync/instal tool must not report "verified" for what it did not verify

A tool that copies a committed file over a live one and prints "verified: read back identical" verifies that it
wrote what it copied — **not** that what it wrote is what was there. Two guards are mandatory when a tree copy
can overwrite a live rulebook:

1. **Refuse to shrink**: destination exists and source is smaller → exit non-zero with both byte counts,
   `FORCE=1` to override.
2. **Say what changed**: `verified: 3 copied, 1 shrank (7,509 -> 5,149 b)` — never "identical" for a file whose
   size moved.

And a negative control that seeds the tree as a strict **subset** of the destination and asserts refusal — a
subset check against destination content, not a size comparison alone.

## Counts and totals

- Always pass an explicit high `--limit`; a default page size silently truncates a count.
- An in-flight job count is a **lower bound**: rows appear as `needs:` resolve. Quote a completed run's total.
- Verify your own claim against the API in the same turn you make it, and say what you ran.
