# Agent profile fold — issue #2877

## Why

The whole `bulk-mechanical-migration` skill directory of the `llgenie-issse-implementer` lane
exists only in the live profile `~/.hermes/profiles/llgenie-issse-implementer/` — the tree at
`agents/llgenie-issse-implementer/skills/` carries no skill at that path, so the lane's migration
rulebook (guard-then-batches order, ratchet selection, leftover-shape gate) is unversioned,
unreviewable and invisible to `git blame`. A lane profile's SKILL.md IS that bot's behaviour, and
this lane holds write credentials. Measured at `main bb29cc9994`: `make -s check-agent-profiles`
reports exactly 1 finding for this lane and it is this `absent-from-tree` directory (#1086 class),
which also blocks AC5 of #2090 and the whole `make check-agent-profiles` exit-0 evidence. A later
security-fix fold removed the flat tree copy (`f45268c8`, #2838) that this directory replaces.

## What Changes

- Fold the live file live→tree byte-identically at
  `agents/llgenie-issse-implementer/skills/bulk-mechanical-migration/SKILL.md`: 9327 b, sha256
  `2c5f8bb26a02`, `version: 1.0.0`, single file (no `references/`, no `scripts/`). The live file is
  read-once (stable sha), copied bytes-only, destination re-hashed to prove identity with the live
  source (the #2327 identity proof). Direction is live→tree, never a live-side edit (#791).
- Restore-in-this-container note: the live profile is not mounted in the agent container, so the
  fold recovers the exact previously-versioned content (git blob `a834a50e`, 9327 b, sha256
  `2c5f8bb26a02`) — the flat copy #1186/#2238 committed and #2838 deleted — as the tree copy. This
  equals the issue's documented live identity byte for byte.
- No script/test/workflow change; every change is the byte-identical skill fold plus the change →
  note → fragment → CHANGES.md record.
