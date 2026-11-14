# Proposal: reconcile-lane-skill-drift

## Why

Issue #2679: `make check-agent-profiles` reports 29 per-lane FAILs — the installed
lane profiles under `~/.hermes/profiles/` disagree with the versioned rulebooks in
`agents/<lane>/` (three finding classes: live-longer, live-lines-missing,
live-edited-not-tree). OpenSpec change #2502 measured that a drifted shared host
downgrades every lane that boots from it (live 1602 vs tree 1200 lines on
llgenie-tester). The gate FAILs every lane while the drift persists.

## What Changes

Re-measurement on origin/main (2026-11-14) classifies all 29 findings into two
groups, and the reconciliation follows the evidence rather than the gate's
default "copy live into the tree" prescription:

1. **27 findings are stale installs, not new knowledge.** All 28 affected files
   are in the touched-file set of `6e3f25ffc` — "fix(agents): retire the
   --force-if-includes drift from the whole instruction surface (issue #2502)
   (#2510)", merged 2026-11-11 21:48Z, AFTER the profiles were installed at
   19:22Z from a pre-#2510 tree. Every drift line is a force-push discipline
   sentence that #2510 deliberately rewrote (plain `--force-with-lease` after a
   fresh fetch; `--force-if-includes` only for amend/integrate pushes whose remote
   tip is an ancestor). The OpenSpec change is the referee: re-folding the retired
   live text into the tree would undo a landed, tested policy decision (#2502).
   These findings are cleared by the tree→live sync the gate itself prescribes
   (`make sync-agent-profile PROFILE=<lane>`), with NO tree content change.
2. **2 findings carry genuinely new live knowledge** (live files edited
   2026-11-14, text never present anywhere in tree history):
   - `agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md`: live §12
     "ci(verify) dispatch-only tickets (the #1505 31-pipeline matrix)" — 16 new
     lines (dispatch-only vehicle rule, batch-card timeout/claim pitfall, live
     workflow state over ledger rows, full shas in evidence, run-window vs
     issue-created_at) plus the referenced `verify-ticket-dispatch-only.md`
     pattern. Folded into the tree. (The live file's ONE re-added
     `--force-if-includes` on the lease line 691 is pre-#2510 drift and is NOT
     folded.)
   - `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/scripts/docs_audit.py`:
     live fixed `make_targets()` to read `mk/*.mk` beside the root Makefile
     (post-make-split issue #2635 family — a Makefile-only grep reports every
     moved target as missing). Folded into the tree.

After this PR merges and the host re-syncs the seven lanes from the tree,
`make check-agent-profiles` reports zero per-lane FAILs.

## Impact

- Affected specs: `agent-profile-drift-gate` (new delta requirement on
  reconciliation direction).
- Affected code: two files under `agents/` (tester SKILL.md, docs-lane
  docs_audit.py). No scripts, gates, or baseline change.
- Host state: seven lane profiles re-installed from the reconciled tree
  (prescribed by the gate message itself).
