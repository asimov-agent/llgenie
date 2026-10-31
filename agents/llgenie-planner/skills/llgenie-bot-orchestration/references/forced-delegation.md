# Forced delegation — idle-capable lanes get work, never a held label (owner 2026-10-30)

Idleness is a defect even when it wears the label "holding". A lane parked on a REAL gate (a producer's direct word, an un-merged base) is parked; a lane that could be doing independent, unassigned, gate-free work is **idle-capable** — and must be forced onto it.

**On every pass, answer this, not just "which lanes are busy":**
- Which lane is idle-capable RIGHT NOW (no held-gate blocker, and there is an open unassigned issue it can complete without that gate)?
- The owner's rule, blunt: "if you delegate to bots and they are still idling, you are supposed to force them to go to work."

**The re-fits that close real gaps (shapes, not incidents):**
- a lane whose active PR sits at a coordination gate (producer half waiting on a co-owner's consumer half) is still idle-capable for OTHER work — force it onto an unassigned live-HF/data issue or a `force`-never-passed publish bug instead of letting it sit on the gate.
- a reviewer with no verdict in flight takes the doc-vs-gate contradictions a recent merge created (a still-open branch that reverts main's shipped fix).
- a lane that filed its own gate bug then parked it under "the file is another lane's to write" is idle-capable — force it onto its own filed finding before accepting the shelter.

**The test of the rule:** a lane whose completion does NOT depend on the blocked gate, sitting with an unassigned open issue it can do, is not waiting — it is idle-capable, and finding that is mine to fix, not observe. "This waits on #919" stops being an excuse for "so I do nothing" the moment there is an issue that doesn't.

## Picking the fit
- Match the issue's domain to the idle lane's role (engine/live-HF-data, reviewer/doc-vs-gate, security/trust, etc.) — the fit is what makes it genuinely delegable.
- Exclude the issues that DO depend on the same gate (a stacked PR behind the un-merged base is parked, not idle-capable).
- Prefer a small, self-contained issue the lane can complete and report, over re-opening the parked fork.
- State "this does not depend on <the gate>" in the dispatch so the lane knows it is forced-doable, not a contradiction of its hold.

## The full-fleet trigger matrix (worked 2026-10-31 pass, main=c09e7b77)

When most lanes are green-bound and the reviewer/tester seem to have "no new issue," the natural PR work IS the
force: the moment a PR is 0-red + MERGEABLE + BLOCKED=review, reviewer (evidence verdict, run id+sha) and tester
(acceptance-criteria exercise, pass/fail per criterion) both have an open, gate-free vehicle — dispatch them there,
it is exactly #1030. Also the per-lane versioning mirrors (#791/#919) are standing gate-free work for any lane whose
own agents/<lane>/ SOUL/skills are live-only: security → #1171, engine-improver → #1097, ci-pipelines →
#1060-flavored #1164, docs → #1104. Match by lane-role first (engine data → engine lane, pipeline gate → pipelines
lane, doc-vs-tree → docs lane, security profile sync → security lane), and keep the implementer's queue for the
misc/general migration + the planner's own #1062.

## Versioning
This rule lives in the planner's SOUL. A SOUL.md edit is the protected-file wall — land the SOUL text by issue + PR under `agents/llgenie-planner/` per #791, and keep the skill text here as the runnable behaviour in the meantime.
