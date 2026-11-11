# Agent profile fold — issue #2177

## Why

`make sync-agent-profile PROFILE=llgenie-product-manager CHECK=1` reports `2 of 2 file(s)
differ`: the tree copy of `agents/llgenie-product-manager/skills/llgenie-product-manager/SKILL.md`
is TRUNCATED (tree 5,985 b / live 12,872 b — the live file is a strict super-set), so a blind
tree→live sync would replace 6,887 b of live behaviour with the shorter copy (#2084-class). The
tree must match the running profile so a rebuild cannot silently downgrade the lane (#2165).

## What Changes

- `skills/llgenie-product-manager/SKILL.md` folded live→tree byte-identically (12,872 b,
  sha `5c074c4d…` == live source).
- `SOUL.md` deliberately NOT folded — the tree copy is the LONGER side (11,677 b vs live 8,550 b);
  folding would lose tree lines (issue step 4). It converges tree→live post-merge.
- No script/test/workflow change; every change is a byte-identical profile fold plus the change →
  note → fragment → CHANGES.md record.
