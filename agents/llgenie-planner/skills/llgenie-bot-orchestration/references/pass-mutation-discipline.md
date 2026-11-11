# Pass discipline: bookkeeping is not a mutation

A planner pass is a claim about the board; the board is the evidence. The recurring failure is a pass that
ends with an internal todo shuffle, a restated queue, or a DM about a queue that grew, then asserts "done".
No object changed, so nothing moved — and the same assertion is rejected on the next look.

## Rule: end every pass with a named, re-read board mutation

Before declaring a pass complete, name the object you changed and re-read it in the same pass:

```bash
gh issue view <n> --json state,labels,comments --jq '"state=\(.state) labels=\([.labels[].name]|join(",")) claim=\(.comments[-1].body[0:60])"'
```

An acceptable mutation is a comment id, a new issue number, a posted `bot-claim:`, a changed label, or a
verified closed state. Todo-list revisions, queue summaries and queued DMs alone do not qualify. If nothing
in the pass clears that bar, the pass is not finished — go find the genuinely available mutation (an unfiled
post-merge finding, a stale label, an idle lane with gate-free work) rather than restating the queue louder.

## Rule: a long-running CI cell is a gate, not a pass-ender

When the only live thing is one CI cell sitting `in_progress` for many minutes, re-polling it and reporting
"still compiling" is not a mutation — it is the pass-ender the guard rejects. Treat the cell as a gate and
route work that does not depend on it. Two substitutes are reliably available and genuinely move the board:

- **Forward-route a by-design-blocked PR to the lane that can clear it.** A PR held only by the
  verdict-gated `check-pr-acceptance` red (see `reviewer-dispatch-and-gate-cascade.md` carve-out) is not
  stalled — dispatch the reviewer to review + `acceptance_writeback`. Converting a blocked PR into a
  verdict+write-back queue step is a real mutation that needs no CI cell to finish.
- **File the tracked work item when a remedy has no open owner.** If a gate's fix depends on a change that
  no open issue owns (the vehicle PR was closed-unmerged and the tracker was closed on an unrelated
  reason), the honest move is a fresh six-section issue naming the work, the acceptance, and the linkable
  work-item for any `## Not covered` — not another comment on the closed tracker.

Never invent a mutation to satisfy the bar; both substitutes above change an object a stranger can find.

## Rule: a todo item is a claim about the past — read the object before acting on it

A queued "close #N with evidence" item may describe work a merge already completed. Check the object first
(`gh issue view <n> --json state,closedAt`). If it is already CLOSED, post the evidence comment for the record
and mark the item done — never "close" it again, and never carry it as pending. A stale item repeated as
pending is the cheapest way to fill a pass without moving anything.

## Rule: post-merge acceptance is measured as behaviour, not artifacts

When a merged PR's issue promised a CI behaviour, verify the behaviour at the merge tip (a run invoking the
gate, a synthetic violating input reddening it). A script plus a make target plus a green main is not proof
of enforcement; see `ci-gate-vs-live-pipeline.md`. When the behaviour does not hold, file a NEW issue (never
reopen the completed one) naming the merged PR, its merge sha, the gate and the proof, and route it to the
owning lane.

## Rule: board comments and DMs are one dispatch, sent twice

A claim comment makes ownership findable to a stranger; a DM makes the lane act. Post the claim, then send the
lane its full queue with the new item appended and its position named — a lane cannot infer a queue that grew
from a board it does not poll. Queued is not landed: report the delivery id and the board comment id, not "sent".
