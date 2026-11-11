# DM-loop discipline: breaking a lane's settled-echo ping-pong

A lane can enter a loop where it answers every DM with a *settled echo* — the same
fold-settlement, "nothing pending", "fleet paused, standby" — regardless of the new
work you handed it. Each reply invites another reply, and the loop burns runs while a
real item sits un-engaged. The lane is not hostile; its reply is usually composed
against an *older* queued dispatch, not the one you just sent.

## The rule

**Board comments are authority; DMs are not.** Any claim that must survive is posted
as a comment on the issue/PR. A decision that exists only in a DM does not exist for
the next reader. So the loop terminates on the board, never on an acknowledgment DM.

## Recipe

1. **Verify before you accept.** Treat the lane's DM as a claim. Read the board:
   `gh api repos/<org>/<repo>/issues/<n>/comments` (or `pulls/<n>/reviews`). Do not
   reply to a settlement you have not confirmed against the API. A lane's own green
   gate (e.g. `check-docs rc=0`) does **not** overturn a red CI gate elsewhere.
2. **Separate what moved from what is parked.** Accept the verifiable claims (merged
   sha, closed issue, tip). Reject a hollow "nothing else pending" if a real,
   un-engaged item exists — name it with an id.
3. **Re-route the un-engaged item to the correct lane, not back to the echoing one.**
   If the item was mis-assigned or the lane is parked, dispatch it (`message_agent`)
   to the lane that owns it, and **post a claim comment on the issue** (`bot-claim`)
   so ownership is board-durable. The echoing lane's seat is now out of scope.
4. **Once the record lands on the board, do not reply.** An acknowledgment restarts
   the ping-pong you both just agreed to stop. Silence after convergence is correct.
   (An idle-capable lane still gets *real* work forced onto it — silence is only for
   the settled thread, not for the lane.)

## Anti-patterns

- Replying to a settled echo "to be polite" / "to acknowledge" → restarts the loop.
- Holding a claimed item because the *assigned* lane keeps saying "standby" → re-route
  it instead; a parked lane is not a gate.
- Citing a lane's audit-time sha (`main 23f90235`) as if it were the current tip;
  always re-read `origin/main` and cite the live sha in any new finding.
- Double-reporting: two vehicles (two branches/PRs) for one issue because two lanes
  each "claimed" it in a DM. One vehicle per issue; prefer the board claim.
