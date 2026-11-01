# security-lane SOUL/skill fold aligns the tree byte-for-byte with live

PR #1256 closes #1255: the security lane's live profile had accumulated drift the tree copy
had not absorbed. Two files under `agents/llgenie-security/` changed.

## What changed

1. **`agents/llgenie-security/SOUL.md`** — restored the dropped canonical mission sentence
   `Message @llgenie-planner with the issue number and the sha. The patch belongs to the lane that
   owns the files.` A `comm -23` comparison showed the tree had deleted a line live still carried
   (tree-only = ∅, live ⊇ repo), so the restoration was byte-safe. The repo SOUL is now
   byte-identical to live (12,044 b).

2. **`agents/llgenie-security/skills/security-scan-ops/SKILL.md`** — folded the curator's
   `## Role artifact (2026-11-01)` section via **union**, keeping the tree-only
   `## When to Use`/`## Standing rules for this lane` rulebook intact (per #791), plus the
   newest-authority live-drift block and the CI-waiting timeout lesson. Zero live lines lost.

Folding used `agent-soul-versioning`'s union rule (live → tree, never the reverse; never a
byte-copy that would delete tree-only rules — issue #1267's lesson).

## Verified

`python3 scripts/check_agent_profiles.py check` → zero llgenie-security rows; `make lint` LINT OK;
container `pytest tests/test_agent_profiles.py` → 136 passed. Head `d5b46f9c`.
