# Tasks

Issue: [#2180](https://github.com/asimov-agent/llgenie/issues/2180)

## Fold the live profile into the tree

- [x] Re-measure tree vs live at freshly-fetched `origin/main` `005d457` → 4 of 9 differ; 3 truncated in tree.
- [x] Copy the 3 truncated files live→tree byte-identically (SKILL.md 100,563 b, post-merge-verification.md 10,353 b, red-job-triage.md 18,782 b).
- [x] Copy the 5 SKILL-linked live-only references live→tree byte-identically (gh-command-mechanics, monitoring-ci-runs, own-domain-audit, pr-state-inspection, verification-evidence-persistence).
- [x] Verify SOUL.md kept-from-tree (live 10,507 b SHORTER than tree 13,634 b; no diff).
- [x] Verify byte identity at the committed head (committed blob sha == live sha == tree sha for all 8 folded files).
- [x] `make check-agent-profiles` (tree-only) green at the head.
- [x] Record the change (agent-wiki note + docs/changes.d fragment + CHANGES.md row, closes #2180).
- [x] Add the openspec/changes/tester-fold-live-2180/ change dir (issue #1807 gate).
- [x] PR ready-for-review, closes #2180, carries AGENTS/BASE/SYNC hygiene lines.
