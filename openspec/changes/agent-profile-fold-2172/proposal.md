# Agent profile fold — issue #2172

## Why

`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` reports `22 of 42 file(s)
differ`, with 20 of them tree-truncated (live richer) — a blind tree→live sync would replace
~56 KB of live behaviour with the shorter copy (#2084-class). The tree copy of the lane's rulebook
is stale; the live profile is the source of truth for this lane's reference files.

## What Changes

- 20 live-newer tracked files under `agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/`
  copied live→tree byte-identically (the tree copy was truncated).
- `SOUL.md` (tree 16,963 b / live 14,575 b) and
  `skills/llgenie-engine-improver/SKILL.md` (tree 107,087 b / live 90,667 b) deliberately NOT
  folded (the tree is the longer side; folding would lose tree lines — they converge tree→live on
  the host via the sanctioned post-fold `sync-agent-profile`, so `CHECK=1` reaches 0 of 42).
- No script/test/workflow change; every tree change is a byte-identical live→tree fold plus the
  change → note → fragment → CHANGES.md record.

## Benefit

A review of `agents/llgenie-engine-improver/` becomes a review of the running agent: the committed
copy stops truncating the lane's behaviour, and a rebuild from the tree is a no-op rather than a
downgrade (issue #2172 / #2090 class).
