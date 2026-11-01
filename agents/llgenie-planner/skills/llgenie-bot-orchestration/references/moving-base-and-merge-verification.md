# The base moves under you: dispatch-time shas and merge-time truth

Two failures of the same kind — trusting a sha recorded earlier instead of measuring the one
that exists now. Both cost a whole bot run when missed.

## 1. Never dispatch an implementer at a chat-, issue- or comment-quoted base sha

`origin/main` advances while you triage, refine and write the dispatch. A base sha that was
current when you filed the issue is routinely one or two merges stale by the time the
implementer fetches. The instruction "branch from `origin/main` @ `<sha>`" therefore hands over
a stale premise, and the resulting PR re-runs CI against a base the gates have already left.

- Rewrite the instruction to **"branch from `origin/main` as fetched at the moment you start"**,
  and tell the implementer to record the sha it actually fetched in its first comment.
- If the issue body or an earlier comment pins a sha, do not silently leave it: measure
  `git ls-remote origin refs/heads/main` immediately before the branch is expected, and post a
  short **BASE CORRECTION** comment on the issue naming the new head — then message the lane so
  it is not branching off the stale value. Both the board and the DM: a correction only in a DM
  does not exist for the next reader.
- Regenerate the `AGENTS:` line to the true current head at the same time.

## 2. A PR's base field is not its merge commit

`gh pr view <n> --json baseRefName,baseRefOid` reports where the PR *was branched from*, which
freezes at open time. It is not where the PR landed. Reporting "still on stale base `<old>`" from
that field is a false finding — the PR may already be merged onto current main.

Read the merge facts instead:

```bash
gh pr view <n> --json state,mergedAt,mergeCommit,mergedBy \
  --jq '{state,mergedAt,merge:.mergeCommit.oid,by:.mergedBy.login}'
git ls-remote origin refs/heads/main            # is the merge commit the current head?
git merge-base --is-ancestor <mergeCommit> origin/main && echo ON-MAIN
```

- `state: MERGED` + `mergeCommit.oid == refs/heads/main` means the work is `main`; do not reopen,
  do not re-dispatch, do not call it un-rebased.
- Post-merge verification is then measured on `main`, not on the PR head: fetch the completed run
  at the merge commit and read its full job matrix; check each acceptance criterion on `main`.

## 3. Every sha you quote is time-stamped

Open every finding with the head you measured it at and the minute you measured it. "X is broken"
without a head is a claim about a moment, not about the branch; the branch may already be green.
When a lane disputes your finding with a different head, re-measure before arguing — the newer
head usually settles it.

## 4. `head_sha` filters return young, incomplete matrices

`gh api .../actions/runs?head_sha=<sha>` right after a push returns runs whose jobs are still
`in_progress` or absent. A red-looking partial matrix is not a verdict; wait for
`status: completed` and read `conclusion` plus every job in `.jobs[]` before declaring anything.
