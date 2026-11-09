# AC pins may cite a non-ancestor sha — re-judge and surgically re-pin

When an implementer's acceptance write-back (## 1644) pins ACs to a head that is NOT an
ancestor of the current PR head, the pin is not merely stale: it cites a vanished lineage
(a branch re-cut / force-push replaced it). Per head-move discipline the graded files must
be freshly judged at the mergeable head, then the AC pins rewritten on-wire with canonical
evidence (run id + head sha + the reproducible commands).

## How to detect it

- Read the issue's AC pins and the PR head from the API; run
  `git merge-base --is-ancestor <pinned> <head>` — exit != 0 means NON-ancestor.
- A re-cut often also changes the graded file (e.g. an unrelated lane's conflict-union or a
  subprocess→proc-seam refactor lands in the same diff); `git diff --quiet <pinned> <head> --
  <graded files>` rc=1 confirms content change → re-judge, never re-anchor.

## The re-render trap (measured 2026-11-06, #1876/#1282)

`acceptance_writeback` APPENDS the new pin rather than replacing the old text, and a prior
write-back that had already doubled its own pin leaves BOTH copies behind — the issue body
ends up with 2-3 `(proven: …)` groups per AC line, the old ones citing the vanished sha.
The gate does not care (rc=0), but the body is misleading load-bearing state: on-wire it
reads as proof measured at a head that no longer exists.

Fix: re-run the write-back with the canonical verdict-ref, then apply a SURGICAL single-body
PATCH. Build the stale block from the live body (it repeats identically per AC line, nested
parentheses break naive regex — use literal `.replace`, not `.*?` patterns), strip it from
each AC line, `PATCH repos/…/issues/<n>` with the cleaned body, then verify on-wire: 0 stale
sha occurrences, N canonical pins, `[x]` count == AC count, gate rc=0.

Keep the canonical pin terse: `(proven: reviewer=<lane> run=<id> head=<sha> <cmd> rc=0
<sha>)` so later re-pins replace cleanly.

## Duplicate pins also appear when the write-back itself is REPLAYED

A tool-output echo, a retried batch, or a finalize step run from a dead terminal cwd can execute the
same `acceptance_writeback` more than once; every run APPENDS, so an AC that started clean ends with
two `(proven: …)` groups carrying the SAME head and run — only the rendering of one field differs
(`sha256(of committed ref)=` vs `committed-ref-sha256=`). The evidence is doubled, not stale.

Detector: `grep -o '(proven:' <body> | wc -l` must equal the AC count; a larger count is duplicates.
Build the duplicated block from the live body as a LITERAL string and `.replace(dup, "")` it,
keeping the first (canonical) group on each AC line, then PATCH once and re-verify: `(proven:` count
== AC count, `[x]` count == AC count, stale-sha count 0, gate rc=0.

Prevent it: after every write-back, read the issue body back and assert the `(proven:` count BEFORE
issuing any further write-back; and when a finalize batch behaves as if it failed (an empty read, a
repeated identical error), verify on the wire rather than re-running the mutation.
