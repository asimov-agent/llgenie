# Reconcile lane skill drift (issue #2679)

Issue: #2679. OpenSpec change: `reconcile-lane-skill-drift`.

## What was measured

`make check-agent-profiles` on origin/main `63b1ce30b` reported 29 per-lane FAILs
across 7 lanes (27 live-longer/live-lines-missing, 2 live-edited-not-tree).
Classification against tree history settled the direction for every finding:

- **27/29 findings = stale installs.** All 28 drift-affected files are in the
  touched-file set of `6e3f25ffc` — "retire the --force-if-includes drift from
  the whole instruction surface" (issue #2502, PR #2510, merged 2026-11-11
  21:48Z). Profiles were installed 19:22Z from a pre-#2510 tree; the live text
  is the retired wording. The OpenSpec change is the referee: re-folding retired
  text would undo a landed decision. Cleared by the tree→live sync the gate
  itself prescribes (`make sync-agent-profile PROFILE=<lane>`); the tester's one
  retired line was overwritten with `FORCE=1` after reading it.
- **2/29 findings = genuine live-only knowledge** (live mtime 2026-11-14, text
  with no `git log -S` ancestor in the tree):
  - tester `llgenie-pr-testing/SKILL.md` §12 "ci(verify) dispatch-only tickets
    (the #1505 31-pipeline matrix)" — folded in;
  - docs-lane `scripts/docs_audit.py` `make_targets()` now reads `mk/*.mk`
    beside the root Makefile (post-make-split #2635 family false positive) —
    folded in.

## Decisions

- Folding §12 pushed tester SKILL.md to 101,144 chars — over the 100,000-char
  skill-writer cap the gate enforces. Per the gate's own instruction (never
  raise the cap), §11 and §12 bodies were moved into
  `references/measured-at-census-pointer.md` and
  `references/verify-ticket-dispatch-only.md`, each kept as a two-line pointer
  section in SKILL.md (94,553 chars). The §12 pointer's missing reference target
  is thereby created instead of dangling.
- New delta requirement: drift reconciliation must first check whether a
  live-only line was deliberately retired by a merged OpenSpec change before
  folding it into the tree.

## Verified state

- `make check-agent-profiles` → OK rc=0 at head (13 host profiles, zero
  per-lane FAILs) after the seven lanes were re-synced from the reconciled tree.
- docs-lane `docs_audit.py` compiles (`py_compile` OK); its mk-glob matches the
  live fix byte-for-byte.
- `make check-docs`, `make openspec-validate NAME=reconcile-lane-skill-drift` → rc=0.
