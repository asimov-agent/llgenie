# Reading workflow-run and check-run state without false "red"/"none"

Querying the GitHub Actions API for a head's CI state has two traps that produce the opposite
of the truth. Both are silent (no error), so a lane ends up posting "gate red" or "no CI" from a
query that simply asked the wrong question.

## 1. `runs?head_sha=` needs the FULL 40-char sha

`/repos/<o>/<r>/actions/runs?head_sha=<sha>` filters on an **exact** head sha. Passing a 10-char
prefix (`head_sha=9fd08a4308`) matches **nothing** and returns `{"total_count":0}` — which reads
as "no runs at this head" when the runs exist and are running. Always resolve the full sha first
and pass all 40 chars:

```bash
FULL=$(gh pr view <n> --json headRefOid -q .headRefOid)
gh api "repos/<o>/<r>/actions/runs?head_sha=$FULL&per_page=20" --jq '.total_count'
```

If a count flips between calls (0 then 4), it is this length artifact, not a race — re-query with
the full sha and trust that number. Never conclude "no CI at head" from a prefix query.

## 2. A gate is red/green per the LATEST check-run of that name, not the first

Re-runs create **multiple check-runs with the same name** at one commit. An earlier `guard`
FAILURE and a later `guard` SUCCESS can both sit at the same head; the newest one is the live
verdict. Reading the first match, or a stale earlier run, reports a red that has already cleared.

```bash
gh api repos/<o>/<r>/commits/$FULL/check-runs \
  --jq '[.check_runs[] | select(.name=="guard")] | sort_by(.started_at) | last | "\(.status) \(.conclusion) \(.started_at)"'
```

Do this per gate name (`guard`, `scope`, `ci-verdict`) and quote the run id / `started_at` you
read. When you discover your earlier post reported the superseded older check-run, post a
terse correction naming the comment you supersede — a stale "gate red" hands the lane a
remedy for a defect that no longer exists.

## 3. Compare shas by prefix, not equality

When testing "is the head still X", use `.startswith(short)` against the live full sha — do not
`==` a 10-char head against an 8-char constant or vice-versa; the mismatch silently fails every
guard clause and the conditional post is skipped as "state changed".
