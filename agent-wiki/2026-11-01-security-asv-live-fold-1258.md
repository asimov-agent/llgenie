# 2026-11-01 — fold live-ahead `agent-soul-versioning.md` live→tree (byte copy)

Work record for #1258 → PR #1261.

## What and why

The live profile's reference `agents/llgenie-security/skills/security-scan-ops/references/agent-soul-versioning.md`
was live-ahead: **live 12,327 b vs tree 10,573 b** at `origin/main 1db367a2` (+1,754).

**Mechanism: BYTE COPY, not union.** A `comm -23 <(sort tree) <(sort live)` strictness check is the normal gate for a
byte-safe fold. It is **NOT** satisfied here (five "tree-only" lines), but those five lines are the OLD wording
fragments of the one bullet the owner's directive re-wrote — the superseded header literally reads
"*Sync is one-way: tree → live, and a live edit after the tree commit is never re-taken backwards*" and
"*never copy the live file back into the tree*", the exact direction the owner corrected. The live file replaces it
with the corrected rule (the live profile is the newest authority; the tree catches up to it; never sync tree over a
live-ahead profile; prove byte-safe folds with `comm -23`) and ADDS the `live-edited-not-tree` timestamp-artifact
lesson (commit, re-run the gate — a surviving row is an mtime artifact, not a failed fold).

So the live file is strictly authoritative and content-preserving; the "tree-only" lines are superseded, not a
distinct rulebook. A byte copy loses nothing in meaning; a union would resurrect the corrected-away direction.
This differs from SKILL.md (PR #1256), where the tree carries a real tree-only rulebook section the live lacks.

## Proof

- Folded file `sha256` live↔worktree identical at build: `61391331441c20e6…`.
- `check_agent_profiles.py check` reports **zero** findings for `agent-soul-versioning.md` after the copy.
- `make lint` → LINT OK.
- Branch head `c10671e8`, PR #1261 (OPEN, not draft, base main).

## Arm

Auto-merge **requested** with SQUASH, but **NOT enabled**: REST `auto_merge.enabled_at` = null,
`mergeable_state` = blocked on the owner-gated review (#1088). `auto=none (pending request, not enabled)`.
Owner approval is the singular merge path.
