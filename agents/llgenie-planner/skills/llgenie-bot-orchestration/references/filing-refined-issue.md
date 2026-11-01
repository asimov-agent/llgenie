# Filing a refined issue — the planner's other lawful mutation

A planner does not implement, but it does create tracked work. Filing a genuinely new, refined
six-section issue (body → labels → `bot-claim:` → dispatch → read-back) is real, verifiable work —
not the "manufactured duplicate" a completion guard forbids.

## When filing is the right move

- A user question or a board observation surfaces a real defect/class that has **no tracked issue**.
- Every lane is idle-capable and the queue is empty: the planner's next action is a new vehicle.
- A completion guard keeps re-firing "no task-relevant mutation" after correct read-back. Filing a
  real, new item is legitimate; filing a **duplicate** of an existing issue, or a code/PR vehicle,
  is the appeasement to refuse (see `verifying-lane-claims.md` §6c).

Do not file when the issue already has an OPEN PR (one-vehicle rule) — that is dispatch territory,
not filing.

## Body shape — `scripts/issue_body.py` SECTIONS, in order

`Problem` → `Why it matters` → `How we fix it` → `Benefit` → `Acceptance criteria` → `Technical`,
with the optional `Not covered` allowed anywhere between `Benefit` and `Technical`. Every acceptance
criterion is a `- [ ]` checkbox a reviewer can tick; a criterion that cannot be ticked is not one.

Validate the order before filing (the render contract rejects out-of-order sections):

```python
sections = ["## Problem","## Why it matters","## How we fix it",
            "## Benefit","## Acceptance criteria","## Technical"]
pos = -1
for s in sections:
    i = body.find(s); assert i > pos, f"order/body fail at {s}"; pos = i
```

## Always pass the body via `--body-file`

Write the body to a scratch file and use `gh issue create --body-file <path>` (same for
`gh issue comment --body-file`). An inline heredoc or `--body "$VAR"` containing backticks,
nested quotes or `$(...)` is eaten by the shell, the command fails, and piping it through
`tail` reports `tail`'s exit 0 — the failure reads as success. Never inline a markdown body, and
never pipe a state-changing `gh` verb through `tail`/`head`; check the `gh` exit itself.

## Validate labels before `create`

An unknown label aborts the create. Enumerate the real set first:

```bash
gh label list --json name --jq '.[].name' | grep -x 'agent:implement'
```

`gh label list` (and every `gh` list subcommand) needs `--json` alongside `--jq`/`-q` — pair them
and it fails with `cannot use --jq without specifying --json`. A planner-filed defect is typically
`agent:implement,bug`; only use a label you have just confirmed exists.

## Claim and dispatch in the same pass

1. Post the `bot-claim:` comment naming the owning lane, the scope, what is **out of scope**, the
   fresh `origin/main` base sha, and what "done" means — one implementer, so no race.
2. `message_agent` the owning lane with the issue id and the same scope (a queued DM is not a landed
   task; the on-record claim is what blocks a second lane).
3. Read back and quote: `gh issue view <n> --json number,state,labels` and the newest comment id
   (`gh api repos/<o>/<r>/issues/<n>/comments -q '.[-1].id'`).

## Pitfalls

- Do not copy a lane's unverified figures (counts, "the file only has X") into the new body — measure
  them from the tree first (`verifying-lane-claims.md` §6c-bis corollary). A false supporting fact
  co-shipped under a true defect steers the fix toward matching the wrong number.
- Measure the pattern with real ids before writing the Problem section (head shas, run ids, failing
  jobs/checks) so the issue carries evidence, not narrative.
