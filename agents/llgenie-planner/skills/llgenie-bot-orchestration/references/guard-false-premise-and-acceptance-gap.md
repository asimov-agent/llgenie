# Guard false-premise loop: verify, find the real owed record, never fabricate

## Trigger

The verification guard (`nerve_verify` / Reflex contract) returns a premise like "no task-relevant mutation was attempted", or pauses read/search/test actions while leaving mutation tools available. It can repeat this premise across several consecutive turns.

## Core rule

The guard's premise is a claim, not a fact. Measure the wire before believing it: comments posted earlier in the same session are still live. Verify one by direct-ID GET. If it is live, the premise is false for this turn — do not re-post the same record (a duplicate trail teaches the next reader to distrust the thread), and never invent a mutation to satisfy the guard.

## Procedure

1. **Disprove or accept the premise.** List the comment ids already posted this session. Verify one by direct-ID GET. Live id ⇒ premise false ⇒ go to step 2.
2. **Inventory genuinely-owed mutations from last-known verified state** (reads may be paused; the records are derivable without new reads):
   - *Acceptance gap* — an instruction was dispatched and the delivery landed, but no acceptance/routing comment exists. The next reader sees the delivery but cannot tell it from an unignored one. Highest-yield finding.
   - *Missing closure sum* — every individual piece was verified (e.g. all N vehicles merged) yet no single consolidated completion record exists anywhere.
   - *Stale premise correction* — an earlier hold or verdict cited state another lane has since changed.
3. **Post exactly one such record.** Non-duplicative, evidence-based, from verified state, and free of merge / auto-merge arm / push to main.
4. **Verify by direct-ID GET**, printing id, issue, author, created timestamp, body length and first line. A POST that exits 0 is not proof it landed with the right body.
5. **Record the verdict**, naming the new id and the reason it was genuinely owed vs. the prior ids.

## Pitfalls

- Satisfying the guard with a repeat post creates duplicate board noise; the correct answer to a false premise is a *different, genuinely-new* record or a written "nothing owed, prior mutation `<id>` stands".
- A dispatch comment is not evidence of acceptance. Bookending every dispatch with an acceptance or closure comment is what makes a board readable to a stranger.
- Reads paused is not work stopped: outstanding records are derivable from state already verified earlier in the session (merge shas, red check cells, routed ids).
- The remedy for a blocked or red PR is a routing/premise comment naming the owning lane and the gate — never a push to another lane's branch and never a merge.
