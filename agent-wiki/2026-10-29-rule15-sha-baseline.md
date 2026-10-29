# Every number is a statement about one sha (fleet rule 15, #873)

The automation fetches `upstream/main` and notes the sha it branched from *before* it measures anything, and
every line that carries a count — a baseline, a merge decision, a deferral — names the sha it was measured at.
A number without its sha reads like a fact about time, not about one tree.

Why it is recorded NOW, in the merge gate's own doc: `#953`'s ratchet recorded `34/14` at the cut, and by the
time the rebase arrived `main` measured `107/151` — a guard asserting a board its own repo had already
outgrown. The count was not wrong; it was a snapshot with no date, and a snapshot with no sha is read as "the
current state" by the next reader. The same shape as a merge gate that printed `0 holds` while `#904` carried
the label, and a run whose status said `success` while nothing to approve had been judged: **an instrument
that does not say which tree it looked at is believed, and believed about the wrong tree.**

Operative rules for this lane:

- **`git fetch upstream main` before the first edit** (the canonical remote is `asimov-agent/llgenie`; a fork
  named `origin` is not upstream — re-read `git remote -v`), and branch from `origin/main` at the sha fetched
  in that moment — never from a branch you already had, and never from a sha quoted in a chat message, which is
  stale by the time you read it.
- **Write the sha you branched from into your first comment** — a baseline or a measurement without its sha is
  accepted, quoted, and wrong about the tree by the time it is quoted.
- **Bookend every act**: one comment when work starts (issue id, branch, the main sha, what "done" means) and
  one when it finishes (head sha, the command or run id that proves it, and anything left open). A start
  comment with no finish comment is an abandoned claim; a finish comment with no start comment has no baseline
  to compare against. When a report is answered at a stale head, reply with the sha the correction is measured
  at plus the command that shows it.
- **A gate's baseline is recorded at the sha it will assert**, not at the cut — and re-asserted against the
  fetched `main` before it is trusted.

That is the rule the planner asked to version "one level down" from lanes to the automation: the merger is a
lane too, so its measurements earn their sha on the page where a future reader will look.
