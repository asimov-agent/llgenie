# Agent profile fold — issue #2172

## Why

`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` reports `22 of 42 file(s)
differ`, with 20 of them tree-truncated (live richer) — a blind tree→live sync would replace
~56 KB of live behaviour with the shorter copy (#2084-class). The tree copy of the lane's rulebook
is stale; the live profile is the source of truth for this lane's reference files.

## What Changes

- 20 live-newer tracked files under
  `agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/` copied live→tree
  byte-identically (the tree copy was truncated).
- 11 `absent-from-tree` live reference files (`non-negotiables`, `own-domain-audit`,
  `profile-live-tree-fold`, `wire-truth-and-make-guards`, …) versioned into the tree for the first
  time — the lane runs under them, so a rebuild without them would drop the instruction.
- `SOUL.md` (tree 16,963 b / live 14,575 b) and
  `skills/llgenie-engine-improver/SKILL.md` (tree 107,087 b / live 90,667 b) deliberately NOT
  folded (the tree is the longer, authoritative side — issue rule 4; their live convergence is
  deferred to provisioning #2165, since a pre-merge tree→live sync is refused because live was
  edited after the tree copy).
- No script/test/workflow change; every tree change is a byte-identical live→tree fold plus the
  change → note → fragment → CHANGES.md record.

## Benefit

A review of `agents/llgenie-engine-improver/` becomes a review of the running agent: the committed
copy stops truncating the lane's behaviour and starts carrying every live reference it runs under,
so a rebuild from the tree is a no-op rather than a downgrade (issue #2172 / #2090 class).
