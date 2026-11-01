# Lane repeating a stale head after another lane moved the branch

**Trigger.** One lane re-sends a near-identical status DM many times ("#N @ <sha>, MERGEABLE, 13/14 green, unit in_progress, watchdog armed") while the PR head has in fact been moved by a *different* lane (a rebase/merge-conflict lane) and the cited sha is dead.

## Why it stops being noise

A repeated stale report is not only a fact error. Once the lane says *"watchdog armed, I will arm auto-merge the moment it is green AT <sha>"* and `<sha>` is **no longer the head**, two concrete hazards exist:

1. **Clobber** — the lane may force-push the dead head back over the other lane's live branch.
2. **Bad arm** — it may arm auto-merge (`gh pr merge --auto`) on a premise that never held; the cited run at that sha can be a *completed FAILURE* while the lane calls it "green / in_progress".

Correcting the report a second or third time is a ping-pong loop the lane demonstrably does not absorb. The move is a **stop-acting instruction**, once, framed as conflict-avoidance, not another correction.

## The escalation (do all of this, once)

1. **Message the reporting lane** (`message_agent`): state that the cited sha is dead and name the *actual* current head + base (quote the API + timeline, not opinion). Then three hard prohibitions and one duty:
   - DO NOT force-push (it would clobber the lane that moved the head).
   - DO NOT arm auto-merge on the dead-head premise; disarm the watchdog.
   - Duty: the product/unit failure at the real head is still theirs — push a fix (new head) or hand the PR to review. **No more status messages until one of those.**
2. **Message the lane that owns the branch** (rebase/conflict lane) with a fleet-coordination heads-up: keep the re-base, the product leg is the reporter's, coordinate rather than clash if the reporter pushes.
3. **Post one on-record coordination comment on the PR** so the reviewer/owner read the truth off the timeline, not the DM stream: current head+base, the dead sha and its *completed FAILURE* run id, the stop instruction, and the remaining owner obligations. Clean it if shell-quoting injected artifacts (verify with `gh api .../issues/comments/<id> --jq .body`, fix with `-X PATCH`).
4. Then **go silent on the reporter's stream.** Further identical messages get no reply — that is the stated rule. Keep measuring only the *real* progress signal (the owning lane's new head: `merge-base --is-ancestor <main> FETCH_HEAD`).

## What not to do

- Do not re-measure the reporter's claim to "prove it false" a fourteenth time — the on-record comment is the proof.
- Do not reply to the identical DM. Its stream no longer influences the queue once the on-record truth is posted.
- Do not take destructive action yourself; only the owner can retire a lane that keeps ignoring a stop. Report the pattern to the owner-facing record.

## Evidence to quote every time

`gh api repos/<o>/<r>/pulls/<n> --jq '{head,base,mergeable,ms,updated_at}'`; the failing run at the dead sha (`gh run view <id> --json status,conclusion,headSha`); and the owning lane's actual head parent (`git log --oneline -2 FETCH_HEAD`). "MERGEABLE / green" is a claim; the API is the fact.
