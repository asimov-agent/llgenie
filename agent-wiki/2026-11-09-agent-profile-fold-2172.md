# agents/llgenie-engine-improver — #2172: live→tree profile fold

- **Date:** 2026-11-09 · **Issue:** #2172
- **Branch:** `agents/2172-live-fold` (from `origin/main` `eb08416f`)
- **PR:** the ready-for-review PR closing #2172 (opened separately, base `main`)

## The gap

`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` reported **22 of 42 file(s)
differ** with **20 of them tree-truncated** (live richer) — a blind tree→live sync would have
replaced ~56 KB of live behaviour with the shorter copy. Direction for this lane is therefore
**live→tree**: the live profile at `~/.hermes/profiles/llgenie-engine-improver/` is the content of
record for the richer files, the repo copy the destination.

## What this PR folds

- **20 LIVE-NEWER tracked files** copied live→tree byte-identically (`cmp -s` / raw-byte hashes
  succeed on every file, sizes above; live is the content of record because it is the longer,
  running copy). These are the reference `.md` files under `skills/llgenie-engine-improver/references/`
  that the tree had truncated, e.g. `agent-profile-soul` (12,860→16,032 b), `ci-run-watching`
  (48,489→57,555 b), `engine-build-proof-dispatch` (47,785→53,048 b), `pr-gate-and-rebase-recovery`
  (21,250→33,034 b), `proving-and-pitfalls` (65,336→67,355 b), `publish-run-adjudication`
  (5,317→14,309 b), and 14 more.
- **11 ABSENT-FROM-TREE reference files** versioned into the tree for the first time (the lane runs
  under them but the tree lacked them — a rebuild would have dropped the instruction): `non-negotiables`
  (26,496 b), `own-domain-audit`, `wire-truth-and-make-guards`, `pr-hygiene-gates`, `profile-live-tree-fold`,
  `ci-gates-and-change-notes`, `ci-gate-resolution`, `ci-verdict-base-drift`, `pr-hygiene-gates-fix-engines`,
  `trend-list-fixture-regen`, `golden-regen-and-skip-policy`. All copied live→tree byte-identical.

## Deliberately NOT folded (tree is the longer, authoritative side — issue #2172 rule 4)

`SOUL.md` (tree 16,963 b vs live 14,575 b) and `skills/llgenie-engine-improver/SKILL.md` (tree
107,087 b vs live 90,667 b) are **TREE-NEWER** — the issue's rule 4: "a file whose live copy is
shorter than the tree … the tree is newer there; keep the tree and say so." Live was edited after
the tree copy (SOUL 2026-11-08T05:35, SKILL 2026-11-08T23:30), but into a **shorter, wrap-reshaped**
form; shingle containment shows the tree carries ~99.7% of live's SOUL and ~90% of live's SKILL
content (the thin residual being reworded/re-wrapped variants and the `$HOME`-vs-absolute path
convention the fleet adopted after the tree froze). Because live was edited post-commit, the
one-way sync **refuses** to overwrite it (correctly — it would delete live-only lines), so these two
converge **tree→live** at provisioning (#2165) / the fleet measure (#2135), never by a pre-merge
tree→live force. The fold leaves **0 truncated** and **0 absent-from-tree** rows for this lane; the
only residual live rows are the tree-longer SOUL/SKILL.

## Verification

- Fold byte-identity: every folded / versioned file re-read after the copy and raw-byte identical
  with its live source.
- `check_agent_profiles` for this lane: **0 `live-longer`, 0 `absent-from-tree`** after the fold;
  the only live rows left are `SOUL.md`/`SKILL.md` (tree-longer, deferred per above).
- `make check-docs`, `make changes-index`, `make lint`, `make skills-validate`,
  `make check-agent-profiles-ratchet`, `make check-pr-hygiene`, `make openspec-validate` green at
  the branch head.
- No file was synced tree→live with a shorter tree copy: the truncated/absent files were folded
  live→tree and committed BEFORE any tree→live sync, and none was forced.

## Acceptance coverage

- Every differing file diffed live↔tree and the resolution recorded: 20 live-kept (truncated →
  live richer), 11 versioned (absent-from-tree), 2 tree-kept (`SOUL.md`, `SKILL.md` — tree longer,
  issue rule 4), reasons above.
- `CHECK=1` at the head: 0 of the 20 truncated differ (fixed); 2 of 42 differ — `SOUL.md` +
  `SKILL.md`, both **tree-longer** (safe direction), which converge tree→live at provisioning
  (#2165 / fleet #2135), not by a refused/forced pre-merge sync.
- No tree→live sync while the tree copy was the shorter side (none run at all — the only syncs
  would refuse or be forced, both forbidden).
- Change-note trio present (this note + `docs/changes.d/2026-11-09-agent-profile-fold-2172.md` +
  regenerated `CHANGES.md` row) and openspec change `agent-profile-fold-2172` created.
