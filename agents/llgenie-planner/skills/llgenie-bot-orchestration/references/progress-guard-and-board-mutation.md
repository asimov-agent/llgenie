# Responding to a progress guard that pauses read-only tools

A supervisor (Nerve progress guard / stall detector) can interrupt a turn with: *"progress guard requires
task-relevant implementation now. Read/search/test-only actions are paused; mutation tools remain."* In that
state every read is denied and only state-changing calls run. This file is how to answer it without breaking
the standing rules that forbid a push to silence a detector.

## The core mechanic: the guard reads THIS turn

The guard scores the **current** turn's tool calls. Two things that feel like compliance but are not:

- **Re-reading the wire to confirm a mutation that already landed is still a read-only turn.** Verifying a
  prior turn's change (`gh issue view … --json labels` after you edited it) does not clear a guard that is
  scoring this turn.
- **Repeating the completion claim a second time is not a mutation.** If you already reported the change and
  the guard fires again, the answer is a new, useful change — not a longer restatement.

## The failure to avoid on both sides

- Never push, cancel a run, or manufacture a dummy commit/test to move the number. A red detector is an
  acceptable state; a cancelled verdict is not. (See the SKILL.md paragraph "An automated progress check is not
  an authority" — that trade is never right.)
- Do not route the guard into idempotent churn: re-adding a label the issue already has, or re-editing a body
  to byte-identical text, changes nothing but `updatedAt`, proves nothing, and a guard may reject it anyway.

## The legitimate forward mutation: route refined-but-unrouted work

The board's own idle-scan gives you a real, non-destructive, always-available mutation. Refined work that no
lane can see is the gap:

```bash
# refined but NOT routed to the implement queue  → idle-capable work
gh issue list --repo <o>/<r> --state open --limit 100 \
  --json number,title,labels \
  --jq '.[] | select((.labels|map(.name))|index("agent:refined")!=null and index("agent:implement")==null)
              | {number,title,labels:[.labels[].name]}'

# routing label set, discovered once
gh label list --repo <o>/<r> --limit 200 --json name --jq '.[].name'
```

Before routing, apply the one-implementer-per-issue rule: skip any candidate with a live `bot-claim:` comment or
an `agent/issue-<n>-*` branch. Then make the mutation and verify it on the wire (exit 0 is not the fact):

```bash
gh issue edit <n> --repo <o>/<r> --add-label agent:implement
gh issue view  <n> --repo <o>/<r> --json number,state,labels --jq '{number,state,labels:[.labels[].name]}'
```

Routing is board state the planner owns — it is not a peer-lane file edit, not a tick on someone else's PR, not a
merge. Other acceptable forward mutations when a route is genuinely not owed: dispatch a lane on a waiting issue,
post a required record/comment on an issue or PR, add a missing `## Acceptance criteria` checkbox group via
`gh issue edit`.

## Compute the owed mutation as the DELTA from the last durable record

When every rail is frozen (all dispatches inside latency, all CI mid-flight, sweep unchanged), the legitimate
mutation is still one you can derive exactly: **what the newest durable record on that board does not already say.**
Memory is not evidence of what a record says — memory holds the board as it was several wakes ago, and the
"correction" you remember owing is usually already posted. So:

1. Read the durable artifact itself and its timestamp (`gh api repos/<o>/<r>/issues/comments/<id> --jq '.created_at,.body'`).
2. Ask what happened **after** that timestamp (a lane dispatched, a head moved, a lane went idle-capable and was forced).
3. Post only that delta. Re-posting the remembered correction when it is already durable is churn; posting the
   delta is a real board change that the next reader needed.

Measured case: a sheet's `idle-capable = <one lane>` line was remembered as stale, but the reconciliation removing it
was already durable — the line was stale for a *different* reason (two lanes forced since that comment, neither of
which it names). The owed mutation was the two dispatches, not the remembered correction.

Corollary: a status-sheet lane's own line is never yours to correct silently — post the delta as a comment on the
sheet's home issue and DM the owner lane the exact replacement line. Do not edit another lane's body.

## Order of operations when the guard fires

1. Decide the board actually needs a change (route / dispatch / record) — do not invent one.
2. Make exactly that mutation in one POST-bearing terminal call.
3. Verify it with a read on the wire.
4. If nothing legitimate can move (everything is genuinely gated), state the refusal: name what the guard asked
   for and why the rule forbids the shortcut. A refusal is a valid ending; churn is not.
