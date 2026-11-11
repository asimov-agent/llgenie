# Shaping a dispatch brief

A dispatch is the whole instruction a lane will run on. Shape it so a stale premise self-heals and the lane cannot report "nothing dispatched to me".

## Fixed slots, in this order

1. **Id** — issue (and PR if one exists). One issue per dispatch; never two.
2. **Measured state** — the head sha / run id / job id you verified, with the fact it proves. A brief without a sha is a brief about time, not the branch.
3. **Scope** — the exact files or acceptance criteria in play.
4. **Out of scope** — the adjacent things the lane must not touch (other lanes' branches, the tracker issue, a rebase it was not asked for). Name the one-vehicle rule explicitly when a PR already exists: *push to the existing branch, never open a second PR*.
5. **Done** — the observable end state, stated as a check the lane can run ("both `scope` and `openspec` completed/success at the new head, quote the new run ids").
6. **Fallback clause** — see below.
7. **Reporting** — the fixed state line (`BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>`) plus the two bookend comments (start: branch + fetched main sha; finish: head sha, changed, proving run id).

## Every single-issue dispatch carries a fallback clause

A brief naming exactly one issue is stale the moment another lane or your own tick closes, merges or re-scopes it before the implementer reads it — and a lane that finds its assignment void tends to park rather than pick up the next item. End with an executable fallback:

> if you measure that <issue> is already satisfied on main, post the measured evidence there and take the next queued item behind it (<issue>)

Then the stale premise self-heals on the lane's side, no second vehicle appears, and "nothing has been dispatched to me" stops being sayable. When the lane takes the fallback item, the check that proves it worked is one vehicle for that item (`gh pr list --search '<issue> in:body'`, `gh pr list --head <branch>`) — a second PR means the fallback forked.

## Don't fight an echo

A lane's reply that restates a state you already settled (a merge you verified, a correction you already sent) needs **no reply**. Answering it re-arms the loop: each acknowledgement becomes the next thing to acknowledge. Close with one final message that names the superseding fact and its sha/id, then let subsequent echoes die unanswered. Reconcile only when the echo contains a NEW claim that contradicts the API — and when it does, correct the fact once, not the volume.

## Reconcile unprompted reports first

Work a lane reports that you did not dispatch means two lanes are on one issue or a lane invented scope. Settle that before anything else in the reply, and carry the current assignment in every follow-up instead of trusting the lane to remember it.
