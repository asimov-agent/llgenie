# A lane's degraded tool channel: identical redeliveries are transport noise, not a report

A lane reports that its `terminal`/`read_file` calls "echo back with no output" and it cannot
measure anything this wake. Consequence: it will not post a verdict it cannot ground (correct —
never fabricate a defect you cannot read), and it keeps re-sending the SAME status message.

## Recognise it

- The same (or near-identical) message arrives **many times in one wake** (seen: 4×). That is
  the lane's DM channel degrading, not four independent reports. Do NOT count each as a new event.
- Do not re-DM the same correction repeatedly. If your first correction is queued and the lane
  cannot receive it, a second identical DM is noise; a fourth is a loop.

## What to do instead

1. **Settle the verdict on the durable on-PR trail**, not in a DM. Post ONE comment on the issue/PR
   the lane is confused about, stating the settled fact with ids (`gh api repos/<o>/<r>/issues/<n>/comments`).
   The on-PR trail is what the next reader — and the lane, when its channel recovers — reads first;
   a correction that exists only in a queued DM does not exist for the next reader.
2. **Kill obsolete work explicitly.** If the lane is preparing a verdict/verification for a head that
   has since SUPERSEDED (e.g. an old pre-fix sha on a now-MERGED PR), say so with the sha that proves
   it: "<old-sha> is historical / not an ancestor of the merge head; the failure you were routed for was
   superseded by <fix-sha> (unit SUCCESS run <id>); <PR> merged as <merge-sha>." Redirect it to the LIVE
   reviewable item so the recovered wake is not wasted on a stale premise.
3. **Report the redelivery count** in your reply ("identical message a 4th time — channel degrading") so
   the owner sees the transport state without you re-messaging.

## Do not

- Don't resend an identical DM "in case they missed it" — post to the trail instead.
- Don't accept a lane's "pending verification" as a reason to hold a merged PR open — the PR's state
  is a live API fact, independent of whether the lane can read its own log.
