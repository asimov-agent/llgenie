# Documentation-maintainer live skill drift fold (self-edit drift)

## What changed

The documentation-maintainer lane's live SKILL.md grew **+348 b** (72,587 vs 71,239) on top of the
#1309 fold, accumulating the lane's own self-edit-drift lesson: the skill-write tools edit the host
profile, not the versioned `agents/<profile>/skills/**` copy, so **every self-improvement pass must
fold live→tree in the same session** (issue → branch → byte-identical copy → `CHECK=1` → PR) or record
the byte delta; and **a "reload your SOUL and skills" instruction is the cheapest drift check** the
lane gets — after re-reading, `cmp` the live skill against the tree copy and treat any size gap as a
finding (new issue + fold PR), because live is what runs and the tree is what a reader trusts. Live is
source of truth; the tree catches up byte-identically (#791).

## Files

- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md` — live→tree
  byte-identical fold (72,587 b). `SOUL.md` unchanged (still aligned, 16,175 b).
- `CHANGES.md` — re-rendered by `make changes-index` (this issue's row).
