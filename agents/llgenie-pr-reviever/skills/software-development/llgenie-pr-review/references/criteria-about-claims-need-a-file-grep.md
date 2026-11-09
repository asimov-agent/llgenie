# A criterion about a CLAIM must be checked against the file, not the PR's own docs

Some acceptance criteria are not about behaviour but about what a file *says* ("no longer claims
30-minute coverage", "the message names the remedy", "the section states X"). These are the ones a
reviewer most often ticks on trust, because the PR body, its agent-wiki note and its OpenSpec proposal
all assert the claim was removed. They are also the cheapest to verify and the most often false.

## The rule
Grep the graded artifact for the exact claim, at the judged head, before ticking anything:

    git show <head>:<file> | grep -nE '<the claimed phrase>'

A PR whose docs say "the file no longer claims 30-minute coverage" while the workflow still reads
`the schedule fires one every 30 minutes` is a REAL defect, not a documentation nit: the criterion's
escape limb ("or the workflow no longer claims …") is unsatisfied, so the criterion fails even though the
behavioural half was fixed. Cite the line number and give the one-line fix instead of ticking.

## A two-limb "or" criterion needs BOTH limbs measured
When the criterion reads "<behaviour> … (or <weaker claim>)", measure the behavioural limb and the
claim limb separately before deciding the criterion is unmeetable. A reviewer who measures only the
behavioural limb (run counts, a cadence figure), sees it fail, and routes the criterion out of scope
has missed that the second limb is often a one-line comment edit that turns the whole criterion true.
Report both measurements: "limb A fails, measured N/day; limb B is available and currently false at
line L — fix is one line". Never route a criterion to `## Not covered` while a one-line limb-B fix
remains available; out-of-scope is for work that belongs to another vehicle, not for work you did not
want to ask the author for.

## See also
- The `(proven: …)` shape the gate accepts, and fixing a ref that reds it:
  `writeback-subset-citation-traps.md` §4 and `verdict-ref-must-name-run-or-rc-sha.md`.
- Surgical re-PATCH that preserves other lanes' existing refs rather than clearing them:
  `writeback-subset-citation-traps.md` "Repair recipe".
