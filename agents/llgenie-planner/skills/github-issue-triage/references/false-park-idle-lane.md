# The false park: a lane that says "nothing has been dispatched to me"

An idle-lane report is a memory claim, not a board measurement. The dispatch record lives in `bot-claim:`
comments on the OPEN issues, and a lane reporting *"zero open PRs, nothing dispatched to me, parked awaiting
dispatch"* will frequently hold a live claim chain the planner wrote itself. Never accept the park from the
chat message; measure it.

```bash
# 1. the actionable queue
gh issue list --label agent:implement --state open --limit 30 --json number,title,updatedAt \
  --jq '.[]|"\(.number) \(.updatedAt[0:16]) \(.title[0:70])"'

# 2. per issue: does THIS lane hold a claim, and what does the claim promise?
gh issue view <n> --json comments \
  --jq '[.comments[]|select(.body|test("bot-claim";"i"))|.body[0:120]]|if length>0 then .[] else "NO claim" end'

# 3. a live vehicle for an already-claimed issue
gh pr list --head "agent/issue-<n>" --state all --json number,state,headRefName
```

Keep the jq filter inside SINGLE quotes and keep `test(...)` simple. Escaping an alternation inside a
double-quoted shell string (`--jq "...test(\"a|b\";\"i\")..."`) breaks the parse, so every issue in the loop
prints `failed to parse jq expression` — which reads like a board problem rather than a quoting problem.

## Finding the frontier

Chained dispatches are recorded as queue-correction comments that spell the whole ordered queue out
(*"YOUR queue is now: A → B → C → D"*). Read the newest correction, then mark off every entry that is
`MERGED`/`CLOSED`; the frontier is the first still-open entry. Check the ISSUE's state, not a PR title — a
queued id often lands under a different PR number.

## Forcing the dispatch

The lane cannot self-assign (one vehicle per lane, claim discipline), so the planner must send it, carrying:

- the frontier id, its live state, and why each predecessor is no longer a blocker — their merge shas;
- the `origin/main` sha to open a fresh worktree from, plus the instruction to read `AGENTS.md` at that sha
  and put the `AGENTS:` line in the PR body;
- one vehicle, PR ready-for-review (never draft), bookend start/finish comments, no merge, no arm unless told;
- a fallback so the dispatch cannot bounce back as another park: *"if you can show with measured evidence that
  part of it is already satisfied on main, update the issue and take the next queued item behind it — but do
  not park."*

An empty-PR board is not an empty lane. If the lane's own queue still has an open item, it is idle-capable and
the park is the defect to fix, not a fact to relay to the owner.
