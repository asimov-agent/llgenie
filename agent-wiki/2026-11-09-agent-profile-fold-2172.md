# agents/llgenie-engine-improver — #2172: live→tree profile fold

- **Date:** 2026-11-09 · **Issue:** #2172
- **Branch:** `agents/2172-live-fold` (from `origin/main` `eb08416f`)
- **PR:** the ready-for-review PR closing #2172 (opened separately, base `main`)

## The gap

`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` reported **22 of 42 file(s)
differ** with **20 of them tree-truncated** (live richer) — a blind tree→live sync would have
replaced ~56 KB of live behaviour with the shorter copy. Direction for this lane is therefore
**live→tree**: the live profile at `~/.hermes/profiles/llgenie-engine-improver/` is the content of
record for the 20 truncated files, the repo copy the destination.

## What this PR folds

- **20 LIVE-NEWER tracked files** copied live→tree byte-identically (`cmp -s` succeeds on every
  file, sizes above; live is the content of record because it is the longer, running copy). These
  are the reference `.md` files under `skills/llgenie-engine-improver/references/` that the tree had
  truncated: `agent-profile-soul` (12,860→16,032 b), `ci-run-watching` (48,489→57,555 b),
  `engine-build-proof-dispatch` (47,785→53,048 b), `pr-gate-and-rebase-recovery` (21,250→33,034 b),
  `proving-and-pitfalls` (65,336→67,355 b), `publish-run-adjudication` (5,317→14,309 b), and 14
  more (`agent-profile-soul`, `ci-openspec-gate`, `engine-build-runtime-cost`, `engine-bump-pr-repair`,
  `engine-image-cells`, `engine-install-leg`, `engine-smoke-tiering`, `evidence-and-run-verification`,
  `host-test-cells`, `issue-filing-and-lane-boundary`, `issue-filing`, `merge-and-followup-recovery`,
  `pin-audit`, `rocm-build-verification`, `test-verification-and-ci-watching`).

## Deliberately NOT folded (tree is the longer side — folding would lose tree lines)

`SOUL.md` (tree 16,963 b vs live 14,575 b) and `skills/llgenie-engine-improver/SKILL.md` (tree
107,087 b vs live 90,667 b) are TREE-NEWER. The live edits there are a strict subset of the
committed copy (verified: every concept the tree carries — the CDI/`engine-launchers` block,
`check-pr-closing`, `check-pr-base`, `Moving-main base-drift`, the worktree rule — is present in
live too; the tree carries them plus the canonical block). They converge **tree→live** via the
sanctioned post-fold `make sync-agent-profile` on the host, which is the only safe direction and
grows the live copy.

## Verification

- Fold byte-identity: every folded file re-read after the copy and `cmp -s tree live` byte-equal.
- Post-fold, after `make sync-agent-profile PROFILE=llgenie-engine-improver` (tree→live, so the two
  tree-newer files grow live to the committed copy), `CHECK=1` reports **0 of 42 file(s) differ**.
- `make check-docs`, `make changes-index`, `make lint`, `make skills-validate`,
  `make check-agent-profiles-ratchet`, and `make check-pr-hygiene` green at the branch head.
- No file was synced tree→live with a shorter tree copy: the 20 truncated files were folded
  live→tree and committed BEFORE any tree→live sync ran.

## Acceptance coverage

- Every differing file diffed live↔tree: 20 resolved live-kept (live longer/current), 2 resolved
  tree-kept (`SOUL.md`, `SKILL.md`), reason recorded above.
- `CHECK=1` at the head: 0 of 42 file(s) differ (after the sanctioned tree→live sync).
- No tree→live sync while the tree was the shorter side.
- Change-note trio present (this note + `docs/changes.d/2026-11-09-agent-profile-fold-2172.md` +
  regenerated `CHANGES.md` row) and openspec change `agent-profile-fold-2172` created.
- `make check-agent-profiles`: 0 same-lane rows across the four live classes at the head.
