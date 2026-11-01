# 2026-11-01 — fold live-ahead `agent-soul-versioning.md` live→tree (byte copy)

Work record for #1267 → PR #1266.

## What and why

The live profile's reference `agents/llgenie-security/skills/security-scan-ops/references/agent-soul-versioning.md`
was live-ahead again: **live 14,260 b vs tree 12,327 b** at `origin/main 06178f15` (+1,933). This is the
#1156-successor fold (prior fold #1261, merge `0c842d24`, closed #1258).

**Mechanism: BYTE COPY, not union** (per this reference's established mechanism from #1261). A
`comm -23 <(sort tree) <(sort live)` strictness check is the normal gate for a byte-safe fold. It is **NOT**
satisfied here (two "tree-only" lines), but those two lines are the OLD wording tail of the fold bullet that
live re-wrote — the superseded tail reads "*Each fold round gets its own issue+PR — content that regenerates
mid-review is the next vehicle*". The live file replaces it with the corrected + expanded retargeting rule
(**when the fold PR is still OPEN and unmerged, re-align its own branch by force-push — one vehicle, not a
second PR**, with the full union recipe and the idempotent tail-anchor note) and ADDS the
`--force-with-lease` needs-the-TRUE-current-remote-sha lease-guard lesson (read `git ls-remote` immediately
before the push; a `(stale info)` rejection is the guard working, not a network fault).

So the live file is strictly authoritative and content-preserving; the "tree-only" lines are superseded, not a
distinct rulebook. A byte copy loses nothing in meaning; a union would resurrect the corrected-away wording.
This is the same conclusion as #1258.

## Proof

- Folded file `md5` live↔worktree identical at build: `752c62249978efd97d37f72e61ace2b9`.
- `comm -23 <(sort -u live) <(sort -u tree)` = **0** (0 live lines lost).
- `check_agent_profiles.py check` reports **zero** findings for `agent-soul-versioning.md` after the copy.
- `make lint` → LINT OK.
- Branch head `074aa5efb49fc6c971a56a99d247c583286d116f`, PR #1271 (OPEN, not draft, base main).

## Arm

Auto-merge **requested** with SQUASH, but **NOT enabled**: REST `auto_merge.enabled_at` = null,
`mergeable_state` = blocked on the owner-gated review (#1088). `auto=none (pending request, not enabled)`.
Owner approval is the singular merge path. (Same as prior fold #1261.)
