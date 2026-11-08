# agents/llgenie-issse-implementer — #2173: live→tree profile fold

- **Date:** 2026-11-08 · **Issue:** #2173
- **Branch:** `fold/2173-live-to-tree` (from `origin/main` `d4e1f376`)
- **PR:** the ready-for-review PR closing #2173 (opened separately, base `main`)

## The gap

`make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1` reported `33 of 64 file(s)
differ` with **30 of them would SHRINK the live profile** — the tree copy under
`agents/llgenie-issse-implementer/` was the truncated side, so a blind tree→live sync would have
destroyed live behaviour (#2084-class). Direction for this lane is therefore **live→tree**: the live
profile at `~/.hermes/profiles/llgenie-issse-implementer/` is the source of truth, the repo copy the
destination.

## What this PR folds

- **30 LIVE-NEWER tracked files** copied live→tree byte-identically (`cmp -s` / `verify_fold_identity.py`
  raw-byte aggregate `identical: True`): `skills/software-development/llgenie-issue-to-pr/SKILL.md`
  (101,499→102,068 b, +45 live lines) and 29 references (e.g. `terminal-and-guard-pitfalls.md`
  3,489→53,073 b, `pr-close-mismatch-recovery.md` 5,145→26,871 b, `gate-red-vocabulary.md`
  10,038→25,078 b, `live-profile-fold.md` 25,769→30,095 b).
- **16 ABSENT-FROM-TREE files** versioned into the tree for the first time (`absent-from-tree` class,
  #1060): 14 `references/*.md` (`acceptance-gate`, `gate-rerun-and-verify`,
  `local-engine-build-verification`, `squash-to-one-commit`, …), the `scripts/check_pr_acceptance_probe.py`
  script, and the whole `skills/software-development/bulk-mechanical-migration/SKILL.md` skill.
- Live fold set is hash-stable across two polls (no mid-write); each copied file re-hashed to prove
  byte identity with its live source.

## Deliberately NOT folded (tree is the longer side — folding would lose tree lines)

`SOUL.md` (tree 11,182 b vs live 8,801 b) and `skills/containerized-repo-verification/SKILL.md`
(tree 28,139 b vs live 27,932 b) are TREE-NEWER; `check-agent-profiles` flags no `live-edited-not-tree`
on them (no live edit after the tree commit), so a live→tree copy is the wrong direction. They
converge tree→live via the post-merge `sync-agent-profile` instead. `rebase-at-worktree-start.md`
(1,427 b) is tree-only (live lacks it) — left alone.

## Verification

Fold byte-identity via `scripts/verify_fold_identity.py` sampled across the fold set; full
`check-agent-profiles` gate: **0 same-lane rows** across `live-longer`/`absent-from-tree`/
`live-lines-missing`/`live-edited-not-tree`; `fold-live-profile.py --check` → 77 same, 2 drifted
(the two tree-newer files), 1 live-missing. `make check-docs`, `make changes-index`, `make lint`
green at the branch head.
