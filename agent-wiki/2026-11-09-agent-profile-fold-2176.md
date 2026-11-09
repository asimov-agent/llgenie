# agents/llgenie-pr-reviever — #2176: live→tree profile fold

- **Date:** 2026-11-09 · **Issue:** #2176
- **Branch:** `agents/2176-live-fold` (from `origin/main` `eb08416f`)
- **PR:** the ready-for-review PR closing #2176 (opened separately, base `main`)

## The gap

`make sync-agent-profile PROFILE=llgenie-pr-reviever CHECK=1` reported **10 of 17 file(s)**
differ with **6 of them tree-TRUNCATED** — the tree copy under `agents/llgenie-pr-reviever/` was
the shorter side (e.g. `SKILL.md` 53,269 b vs live 108,599 b), so a blind tree→live sync would
have REPLACED ~105 KB of live behaviour with the truncated copy (#2084-class). Direction for this
lane is therefore **live→tree**: the live profile at
`~/.hermes/profiles/llgenie-pr-reviever/` is the source of truth, the repo copy the destination.

## What this PR folds

- **6 LIVE-NEWER tracked files** copied live→tree byte-identically (`cmp -s` everywhere):
  `skills/software-development/llgenie-pr-review/SKILL.md` (1.26.0→1.28.0, 53,269→108,599 b) and
  five references — `agent-profile-tree-review.md` (10,882→16,547 b),
  `base-and-merge-integrity.md` (10,424→23,791 b), `gate-auditing.md` (11,468→16,087 b),
  `local-verification.md` (5,720→15,077 b), `standing-rules-for-this-repo.md`
  (59,642→77,327 b).
- **46 ABSENT-FROM-TREE references** versioned into the tree for the first time (#1060 class):
  `acceptance-*`, `authoring-versioned-soul-change.md`, `body-gate-agents-base.md`,
  `ci-check-state-polling.md`, `verdict-*`, `writeback-*`, `review-recipes-by-pr-type.md`,
  `phantom-check-pr-base-fleet-merge.md`, `dispatch-red-attribution-vs-leg-log.md`, and 34 more —
  plus the `templates/finding-verification.py` executable the SKILL names.
- Live fold set is hash-stable; every folded file re-hashed to prove byte identity with its live
  source.

## Deliberately NOT folded (merges / tree-newer / tree-only)

- **`rebase-sweep.md` — MERGED**: tree carried 2 hardcoded `/home/asimov/` path lines the live
  copy replaces with `"$HOME"`-relative ones (`live-lines-missing` class). Folded the live form
  into the tree so a rebuild keeps both; now byte-identical to live.
- **`SOUL.md` (tree 16,309 b vs live 11,887 b) — TREE-NEWER**: `check-agent-profiles` flags no
  `live-edited-not-tree`, so a live→tree copy is the wrong direction; it converges tree→live via
  the post-merge `sync-agent-profile`.
- **`read-the-failing-job-log-pointer.md` (1,330 b) and `rebase-at-worktree-start.md` (1,477 b) —
  TREE-ONLY** (live lacks them): left alone; the post-merge sync adds them to live. Kept because
  the tree has no counterpart to lose.

## Verification

Fold byte-identity proven with `cmp` per file (52 folded identical, 0 mismatch); the comparator at
the fixing head reads **3 of 17 differ** — exactly the tree-newer `SOUL.md` and the two tree-only
references, which are the post-merge sync's job, not the fold's. `check-agent-profiles`
**0 same-lane rows** across all four live classes; every reference the folded SKILL names exists in
the tree. `make check-docs`, `make changes-index`, `make check-agent-profiles-ratchet` green at the
branch head.

## Acceptance coverage

- **AC1** (diff live↔tree + record resolution): every differing file resolved above.
- **AC2** (fold committed, PR closes #2176): this PR.
- **AC3** ("`CHECK=1` reports **0 of 17** differ at the fixing head"): NOT provable at this PR's
  pre-merge head. The comparator reads `3 of 17 differ` because the fold deliberately leaves
  `SOUL.md` tree-newer and two references tree-only — copying them would lose tree lines. `0 of 17`
  is reachable only after the post-merge tree→live sync (#1724 gates it), exactly as the sibling
  fold #2173 documented.
- **AC4** (no tree→live sync while the tree copy was shorter): honoured — no file synced tree→live
  here; the fold lands first.
- **AC5** (change-note trio): this note + `docs/changes.d/` fragment + `CHANGES.md` row.
- **AC6** (`make check-agent-profiles` green): 0 same-lane rows (the whole-gate rc=1 is other
  lanes' ambient `absent-from-tree` drift, each folded by its own per-lane issue under #2135).
