# llgenie-security — #1784: sync-gate parity gap closed (idle-audit reference reaches the live profile)

- **Date:** 2026-11-06 · **Issue:** #1784 (`continuous-improvement` + `agent:refined`, planner dispatch)
- **Branch:** `agent/issue-1784-idle-audit-sync` (from `origin/main` `c9f17d961b`)
- **PR:** the ready-for-review PR closing #1784 (opened separately)

## The gap

`agents/llgenie-security/references/idle-audit.md` (the concluded idle-audit definition, landed into the
tree by merged #1581) was **tree-only**: it existed in `agents/llgenie-security/references/` but the live
`llgenie-security` profile's `references/` directory did **not** exist. `make sync-agent-profile
PROFILE=llgenie-security CHECK=1` red'd `references/idle-audit.md (missing in the profile)` — an
untracked parity gap: the tree promised a reference the running agent did not carry.

## Why tree→live had not delivered it already

`sync-agent-profile` (tree→live, `scripts/agent_profile_sync.py`) **refused wholesale** because the live
profile was richer on two files (`#1724`: never write-sync a richer live; fix the TREE first):

- `SOUL.md`: live 13259 b vs tree 12790 b at the stale reading
- `skills/security-scan-ops/SKILL.md`: live 60766 b vs tree 51551 b

A sync would have truncated a live rulebook. That truncation refusal is what blocked the reference from
ever reaching the live profile.

## The fix (this lane's #791 versioning duty; no code/workflow/scan change)

1. **Fold live→tree** the live-richer `skills/security-scan-ops/SKILL.md` verbatim via
   `fold-live-profile.py --profile llgenie-security --copy` (`#791` one-way direction; these are this
   session's own live gate lessons). (`SOUL.md` already matched live at the real `origin/main` tip —
   the "12790" differ was the stale in-repo checkout, not the tree.)
2. **Run the sanctioned tree→live sync** `agent_profile_sync.py --profile llgenie-security --root
   <worktree>` — now unblocked — which delivered `references/idle-audit.md` into the live profile
   (created `references/`).
3. **Read back:** `cmp tree reference live reference` → identical; `sync-agent-profile CHECK=1` →
   `OK: 13 file(s) ... match ... byte for byte`. Parity gap closed.

## Proof

- live `/home/asimov/.hermes/profiles/llgenie-security/references/idle-audit.md` exists, 3132 b,
  identical to the tree copy (`cmp` clean).
- `scripts/agent_profile_sync.py --profile llgenie-security --check --root .worktrees/1784-idle-audit-sync`
  → `[agent-profile] OK: 13 file(s) ... match ... byte for byte`.
- No scan, workflow, or code file touched; no security finding; no strengthening/weakening.

## Out of scope

The SKILL multiply-fold is the mechanism that unblocks the sync (fix-the-TREE-first per #1724), not a
separate content change. No other lanes' files touched.
