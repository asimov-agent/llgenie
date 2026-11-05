# Auditing prose against the tree (stale-reference drift)

Structural gates are file-oriented, not prose-oriented. The census counts tracked files,
`check-docs` checks change-note indexing, `check-wiring` checks wiring — all can pass while
documentation still names a workflow or script that the tree no longer contains. That gap is the
signal to hunt on an alignment audit.

## The defect class

A doc that cites a **retired or renamed** artifact as *current/active* is the same defect as a
census taken before a merge: read as fact, it sends the next operator to reconcile against a dead
file — they rebuild a dead pipeline or file a wrong "missing" finding. It also falsifies adjacent
claims (a `secrets: inherit` note naming the wrong target reads as a secret-rotation bug).

## Procedure

1. Measure at a named sha on a clean base (`git worktree add /tmp/audit origin/main`), never on a
   dirty checkout.
2. Run the structural gates as usual — they are necessary, not sufficient.
3. Extract candidate filenames from the prose: `grep -roh '\b[a-z0-9_-]*\.\(yml\|yaml\|sh\|py\)'`
   across the docs you own, then de-duplicate.
4. For each candidate, confirm existence at the measured sha:
   `git ls-tree -r <sha> .github/workflows/` (and the matching dir for scripts). Absent = candidate
   stale reference.
5. Separate legitimate cross-repo references (a workflow owned by another repo, cited as such) from
   in-repo claims. Cross-repo citations are correct and must NOT be changed — name them as exempt in
   the finding.
6. For each genuine stale in-repo reference, trace when it was removed
   (`git log --diff-filter=D -- <path>`) and what replaced it, then file a docs-only finding.

## Finding shape

- Cite each stale line with file:line and the replacement artifact.
- State that the structural gates are green (so the reviewer knows this slipped past them and why).
- Call out the retirement commit and the sole surviving producer.
- Explicitly exempt cross-repo references and leave config/test files (e.g. a pause-list asserted by
  a test) to their owning lane rather than folding them into a docs PR.
- Acceptance: a grep after merge shows only historical-context mentions; `git ls-tree` confirms the
  deletion was not reverted; the structural gates stay green on the PR head.
