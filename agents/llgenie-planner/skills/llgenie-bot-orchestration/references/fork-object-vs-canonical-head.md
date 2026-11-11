# "Rebase landed, head moved to <sha>" — object exists vs canonical ref advanced

A lane reporting a rebase/force-push routinely names a sha that *resolves* but did not move the
canonical PR. The two facts are independent. Prove the advance on the canonical repo only; never
infer it from the object existing.

## The insidious variant

The quoted sha returns `HTTP 200` from `gh api repos/<o>/<r>/git/trees/<sha>` (or `git/commits/<sha>`),
and `git cat-file -t <sha>` says `commit` — so a casual check looks "real, it landed." But it was
pushed to the **fork** (`andyholst/llgenie`), whose `git/trees/<sha>` also 200s, while the canonical
branch and PR ref stayed at the old sha. A fork push does not advance the canonical PR.

## What actually proves the head moved

```bash
git ls-remote origin refs/heads/<branch>          # must equal the quoted sha
git ls-remote origin refs/pull/<n>/head           # must equal the quoted sha (the PR's own head)
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha[0:12],base:.base.sha[0:12],mergeable}'
git ls-remote origin | grep -i <quoted-sha> || echo 'sha on NO canonical ref'   # fork object notwithstanding
git ls-remote <fork-url> refs/heads/<branch>      # the fork branch can point elsewhere too
```

If the canonical `refs/heads/<branch>` or `refs/pull/<n>/head` still points at the old sha, the
"rebase landed / head moved" claim is **false** — even though the object is fetchable. Say so plainly
and re-anchor the lane: re-anchor on `origin/main`, push to `refs/heads/<branch>` in the canonical
repo (asimov-agent/llgenie), not the fork; a fork push is invisible to the PR.

## Corollary — timestamp the lane's own bookends

A lane's "bookend" comments often predate the claim by many minutes and describe an earlier push
state. Check `gh api repos/<o>/<r>/issues/comments/<id> --jq .created_at`; bookends older than the
claimed push do not corroborate it.

## When the object is genuinely nowhere

If the sha returns 404 from the tree/commit API and appears on no `refs/heads/*` or `refs/pull/*`,
it is a phantom head (pre-rebase or abandoned) — see `verifying-lane-claims.md` §6i-quinquies. The
fork-resolvable-but-unnamed case above is the harder one because object existence masks it.

## Positive signal to separate from the false one

While a lane's "head moved" claim is false, the **real** live producer can still be active at the
unchanged canonical head. Enumerate runs at the actual `headRefOid` and read the specific run/job
(`gh api .../actions/runs?head_sha=<real-head>` then the run's jobs) — a real `engine-build`
`in_progress` at the true head is the witness channel, independent of whatever stale sha the lane
quoted. Don't let refuting the sha-claim blind you to the live run that is genuinely deciding.
