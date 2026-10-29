# Forced delegation — idle-capable lanes get work, never a held label (owner 2026-10-30)

Idleness is a defect even when it wears the label "holding". A lane parked on a REAL gate (a producer's direct word, an un-merged base) is parked; a lane that could be doing independent, unassigned, gate-free work is **idle-capable** — and must be forced onto it.

**On every pass, answer this, not just "which lanes are busy":**
- Which lane is idle-capable RIGHT NOW (no held-gate blocker, and there is an open unassigned issue it can complete without that gate)?
- The owner's rule, blunt: "if you delegate to bots and they are still idling, you are supposed to force them to go to work."

**The three re-fits that closed a real gap:**
- engine-improver -> #974 (trend-matrix reads live HF, the data path) + #990 (publish-agent-image force) while its #1029 producer half sat at the ci lane's consumer-half gate.
- pr-reviever -> #976 + #988 (doc-vs-gate contradictions from the author-gate merge) with no verdict in flight.
- architect -> #973 (its own filed `agents.parents[1]` path bug) which it had parked under a "the file is another lane's to write" shelter.

**The test of the rule:** a lane whose completion does NOT depend on the blocked gate, sitting with an unassigned open issue it can do, is not waiting — it is idle-capable, and finding that is mine to fix, not observe. "This waits on #919" stops being an excuse for "so I do nothing" the moment there is an issue that doesn't.

## Picking the fit
- Match the issue's domain to the idle lane's role (engine/live-HF-data, reviewer/doc-vs-gate, security/trust, etc.) — the fit is what makes it genuinely delegable.
- Exclude the issues that DO depend on the same gate (a stacked PR behind the un-merged base is parked, not idle-capable).
- Prefer a small, self-contained issue the lane can complete and report, over re-opening the parked fork.
- State "this does not depend on <the gate>" in the dispatch so the lane knows it is forced-doable, not a contradiction of its hold.

## Versioning
This rule lives in the planner's SOUL. A SOUL.md edit is the protected-file wall — land the SOUL text by issue + PR under `agents/llgenie-planner/` per #791, and keep the skill text here as the runnable behaviour in the meantime.
