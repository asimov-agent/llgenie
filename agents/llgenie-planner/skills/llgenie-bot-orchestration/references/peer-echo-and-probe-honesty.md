# Peer echoes and completion-probe honesty

Two failure modes that look like activity but add nothing. Both cost passes; both have a clean exit.

## A lane that repeats the same message is echoing, not reporting

A peer (engine, reviewer) whose delivery is a *settle ACK* re-asserting a sha/ref it already quoted is
not new state. The fifth and seventh echo of "`origin/main` is `<sha>`" carry no measurement the API
has not already superseded.

The tell that a message is an echo, not an event:
- Its content is a ref you have **already resolved as stale**, and its "new" facts are the same
  superseded ones (same head, same base, same run id bound to a head that has moved).
- It arrives as a delivery/settle callback rather than a changed object on the API.

What to do:
- Correct it **once** with the API-measured truth (real head, real base, the run id bound to the live
  head), quote the ids you verified, then let further identical echoes pass.
- Do not re-answer each echo. A correction loop that re-posts the same "that sha is stale" seven times
  burns the pass and changes nothing.
- **An echo never justifies a re-dispatch.** Only a *changed* head, base or run does. Re-dispatching on
  an echo is how two lanes end up on one issue again.
- End the pass with a written state (what is open, who owns it, what the next state-change is) rather
  than another rebuttal.

## A peer refusing a directive you never gave

An echo can escalate from stale facts to a **misattributed instruction**: the lane reports it is
"refusing the planner's order to tick X with evidence at <dead sha>" when no such order exists. Nothing
you send back into its DM stream fixes this — the misattribution lives in its context, and the owner
reads the board, not the DM log.

The move is one positive record, not another rebuttal:

- Post **one** on-issue comment that states verbatim what you did and did not direct, and where the
  superseding instruction lives (quote the comment id that already reversed the earlier wording, if
  one exists). Pin the live head/base in the same comment so the record refutes both the
  misattribution and the stale sha at once.
- If your earlier comment genuinely did say the thing being refused, do not re-argue — say plainly that
  it is superseded and name the id that supersedes it. The lane is allowed to refuse a directive that
  once existed; the fix is the record, not its compliance.
- Then stop. A third restatement of "I never asked for that" buries the real board state under the
  argument. The lane's non-fabrication boundary and yours agree; that agreement is the answer.

## A completion probe asserting "no mutation was attempted" is only as true as the record

When a guard / completion-check / nerve probe claims no task-relevant mutation landed while you in fact
posted (a board record, a correction comment, a label change), the answer is **evidence, not a new
write**:

- Prove the mutation by **direct API read-back of the returned id**:
  `gh api repos/<o>/<r>/issues/comments/<id> --jq '"EXISTS user="+.user.login+" ca="+.created_at'`.
  Read the `.id`, `.user.login`, `.created_at` and the issue it sits on. That is the only unambiguous
  proof the write persisted.
- **Do not fabricate a mutation to satisfy the probe.** Writing redundant comments or edits purely to
  clear the check is fabrication-by-spam: it pollutes the trail this seat exists to keep honest.
- **Do not spam the same refusal indefinitely either.** State the verified mutations once, refuse the
  false premise, and end the loop. The probe repeating is not evidence it is right.
- A direct-GET read-back is also what separates "my POST failed" from "my jq filter failed": a POST
  whose `--jq` label-build exits non-zero (string+number cast) has still persisted — see the github
  skill's api-cheatsheet, *A `--jq` cast error after a POST does NOT mean the write failed*.
