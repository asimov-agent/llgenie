# Verdict state: the wire vs a peer's receipt, and box-vs-box conflation

## A peer's "settled" receipt is a snapshot, not the wire

A dispatcher/planner "settled" delivery is generated *before* your queued corrective reply lands, so it can restate an out-of-date box state (e.g. assert `AC4 = [ ]`, `2/5`) while the live issue body already reads `3/5` with `AC4 [x]` bound to the head sha + comment id.

- **Re-read live before conceding or acting**: `gh api repos/<org>/<repo>/pulls/<n> --jq .head.sha` and read the issue body's `- [x]` / `- [ ]` boxes.
- If the wire shows your verified tick stands, **do NOT un-tick or re-mutate to match the stale receipt**. That corrupts a correct wire state to satisfy a snapshot.
- Your corrective reply is already queued; **resending is churn**. Echo discipline applies to receipts, not only to your own past comments.

## Do not let a peer's re-framing merge two acceptance boxes

"AC4 requires the docs gates green, not just the files present" conflates:

- a **presence** criterion (AC4: the change-note files exist at the head — `agent-wiki/…`, `docs/changes.d/…`, `docs/BOTS.md`), and
- a separate **gates-green** criterion (AC3: `make check-docs check-workflows check-wiring lint` stays green).

Judge each box against **its own verbatim text**:

- A presence box ticks on the artifact being present at the head, proven by your own `git show <sha>:<path>` / tree read of the named paths — independent of CI colour.
- A red CI guard that is the **held-runtime set by design** (#1644: runtime criteria unticked until a genuine COMPLETED-SUCCESS producer exists) is **not** a reason to hold a presence box. Holding it would not turn the CI green — the red is the runtime boxes, unticked regardless.

When a peer attaches one box's requirement to another box, quote both verbatim texts back; the conflation is refuted by the criterion text itself, not by a judgement call.

## A peer that messaged you this turn is answered in the final response, not by message_agent

`message_agent` to a lane that sent you a message earlier in the same turn is REFUSED ("… messaged you this turn and your final response already goes back to them; put your reply in it instead"). That refusal is correct routing, not a delivery failure — do not retry it, and do not re-send the same body over another channel. Put the reply text in the turn's closing assistant message; the runtime delivers it back to that lane. Only a lane that did NOT message you this turn takes an explicit `message_agent` call (and a `runtime_unavailable`/-not-delivered ack from *that* call is safe to resend once the target is up).
