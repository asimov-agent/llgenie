# A dispatched task is LANDED only when the branch proves it — a dispatch comment is not evidence

Posting `BOT <lane> · #<id> …` and DMing the implementer makes a task *owned*, not *done*. When
you report progress (or the guard demands a real mutation), the evidence is the branch, measured
live — never the dispatch comment existing and never the lane saying "done". Distinguish three
states and quote the object that proves which one holds:

1. **Queued** — a dispatch comment + DM exist. Nothing changed on the branch.
2. **Started** — the fork branch head has **moved** since the dispatch (compare the sha you saw at
dispatch to the current ref). Movement alone is not the fix; it only proves a push happened.
3. **Landed** — the moved head **contains the specific artifact the dispatch asked for**, and its
   chain is clean (parent == current main tip or the PR's base, no foreign commits).

```bash
# measure head movement (state 2)
gh api repos/<o>/<r>/git/ref/heads/<branch> --jq '.object.sha[0:11]'
gh api repos/<o>/<r>/commits/<head> --jq '{sha:.sha[0:11],parent:(.parents[0].sha[0:11]),msg:(.commit.message|split("\n")[0])}'
# prove the fix artifact is present (state 3) — e.g. the fixture now carries the key it lacked
curl -sL -H "Authorization: Bearer $(gh auth token)" \
  "https://raw.githubusercontent.com/<o>/<r>/<head>/<path>" | grep -c '<key>'
# chain clean off main?
gh api "repos/<canonical>/<repo>/compare/main...<head>" --jq '{status,behind_by,ahead_by}'
```

Report the landmark as state→state ("dispatched → fix landed, CI in progress") with the head sha,
the artifact count, and the compare result — that is a real board mutation. "I dispatched it" with
no head measurement is a claim about your own action, which the guard and the owner both reject.

## The fork is the branch, not the canonical ref

When a lane pushes from a fork, the moved ref lives at `repos/<fork-owner>/<repo>/git/ref/heads/...`
and the canonical `repos/<canonical>/<repo>/refs/heads/...` may not exist for that branch — read the
head from the fork (or from `.head.repo`/`.head.sha` on the PR), then verify its content at that sha.
