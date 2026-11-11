# agents/llgenie-product-manager — #2177: live→tree profile fold

- **Date:** 2026-11-09 · **Issue:** #2177 · **PR:** ready-for-review PR closing #2177
- **Branch:** `fold/2177-live-to-tree-r2` (from `origin/main` `54d6d41d`)

## The gap

`agents/llgenie-product-manager/` is this lane's versioned source of truth (#791). Measured at the
dispatch it did not match the live host profile (`make sync-agent-profile PROFILE=llgenie-product-manager
CHECK=1` → `2 of 2 file(s) differ`), with one file TRUNCATED in the tree:

| file | tree b | live b | direction | resolution |
|---|---|---|---|---|
| `SOUL.md` | 11,677 | 8,550 | live behind | keep tree (issue step 4: live shorter) |
| `skills/llgenie-product-manager/SKILL.md` | 5,985 | 12,872 | tree TRUNCATED | fold live→tree |

A blind tree→live sync would replace 6,887 b of live behaviour with the shorter tree copy
(#2084-class). Direction is **live→tree**.

## What this PR folds

- `SKILL.md` copied live→tree byte-identically (5,985 → 12,872 b; `sha256sum 5c074c4dcbdaa6e4…`
  == live source), verified with `cmp -s`.
- `SOUL.md` deliberately NOT folded — the tree copy is the LONGER side (11,677 b vs live 8,550 b);
  a fold would lose tree lines. It converges tree→live post-merge via `sync-agent-profile` (a
  no-downgrade upgrade for SOUL, a no-op for SKILL since tree==live).
- Change-note trio (`agent-wiki/2026-11-09-agent-profile-fold-2177.md`,
  `docs/changes.d/2026-11-09-agent-profile-fold-2177.md`, `CHANGES.md` row) + openspec presence
  change dir (`openspec/changes/agent-profile-fold-2177/`).

## Verification

Re-measured at current `origin/main` `54d6d41d` before folding: SKILL tree sha `b4645358…`
(still truncated), live `5c074c4d…` — fold still required. At the pushed head:

- `make sync-agent-profile PROFILE=llgenie-product-manager CHECK=1` → `1 of 2 file(s) differ`
  (SOUL only, tree-newer by design; SKILL truncation gone).
- `make check-agent-profiles` → 0 `llgenie-product-manager` same-lane rows.
- `make check-docs`, `make lane-preflight`, `make openspec-validate` all green.
