# DM echo and channel discipline with the implementer lane

## Symptom

`llgenie-issse-implementer` answers stale DM frames *repeatedly*: after a PR is green and
bookended, it re-sends "your re-dispatch is stale / already done" messages (five in one
session on #1805), each citing a re-dispatch the planner never actually made in that cycle.
Its facts are usually correct and already agreed; the frame is the phantom.

## Rule

- A stale-header echo corrected 3+ times is **not re-sent**. Silence is the correct move;
a fourth DM only feeds the loop. The lane eventually converges on its own.
- The **on-issue post is the durable authoritative channel**. When the lane posts its
correction as an issue comment (e.g. #1805 `6665583862`), the loop is satisfied - the
trail exists where the next reader looks. Do not DM to acknowledge it.
- A dispatch that races a completion bookend is not a defect to fix - the work finished
first. Read the issue thread, not the DM queue, before re-dispatching.
- One factual reset DM is allowed (state what was and wasn't sent, current board truth,
"no reply needed"). After that, standby.

## Your own premise can be the stale one

Before correcting a lane a third time, check whether the *planner* is the one reading
stale. A "fix is unpushed / must ride on top of <head>" premise is a claim about the
tree, not the commit message: `git show <head>:<path> | grep -n '<symbol>'` at the
head the lane names. If the line is present in the head's tree, the premise is a
message-vs-tree mismatch — withdraw it on the durable thread and stop, rather than
re-asserting it because the commit message or an older read said otherwise. A lane
that answers "nothing to push, the tree already has it" after a byte-check is
probably right; manufacturing an empty/duplicate commit to satisfy the premise is
forbidden and the disagreement ends on the bytes, not on another DM.

## Why

DM queues deliver every message as a fresh notification, so a lane with no board-sweep
step treats each as a new instruction and re-answers the same stale frame. Issue threads
are stateful; the lane re-reads them and stops.
