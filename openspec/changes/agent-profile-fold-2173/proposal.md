# Agent profile fold — issue #2173

## Why

`make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` reports `33 of 64 file(s)
differ`, with 30 of them tree-truncated (live richer) — a blind tree→live sync would destroy live
behaviour (#2084-class). The tree copy of the lane's rulebook is stale; the live profile is the
source of truth for this lane.

## What Changes

- 30 live-newer tracked files under `agents/llgenie-issse-implementer/` copied live→tree
  byte-identically (SKILL.md + 29 references).
- 16 `absent-from-tree` files versioned into the tree for the first time (14 references, the
  `check_pr_acceptance_probe.py` script, and the whole `bulk-mechanical-migration` skill).
- `SOUL.md` and `containerized-repo-verification/SKILL.md` deliberately NOT folded (tree is the
  longer side; folding would lose tree lines — they converge tree→live post-merge).
- No script/test/workflow change; every change is a byte-identical profile fold plus the change →
  note → fragment → CHANGES.md record.
