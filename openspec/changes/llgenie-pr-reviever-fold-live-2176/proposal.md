# llgenie-pr-reviever-fold-live-2176 — proposal

Issue: [#2176](https://github.com/asimov-agent/llgenie/issues/2176)

## Why

The lane has been running a **richer live profile** than the versioned tree under
`agents/llgenie-pr-reviever/` — a rebuild from the tree would have silently downgraded the agent
(#2084-class). This PR folds **live → tree** so the committed behaviour matches what the lane runs.

## What Changes

- 6 tree-truncated tracked files copied live→tree byte-identically: `SKILL.md`
  (`1.26.0 → 1.28.0`) and five references (`agent-profile-tree-review.md`,
  `base-and-merge-integrity.md`, `gate-auditing.md`, `local-verification.md`,
  `standing-rules-for-this-repo.md`).
- 46 absent-from-tree references versioned for the first time plus the
  `templates/finding-verification.py` executable the SKILL names.
- `rebase-sweep.md` merged (adopted the live `"$HOME"`-relative path form).
- Tree-newer / tree-only files kept: `SOUL.md` (tree > live, no live-edit), the two tree-only
  references.
- #1123 change-note trio + openspec change (`skip_specs: true`, content-sync fold) so the #1807
  openspec-presence gate for the `agents/` path is satisfied.

## What Doesn't Change

- No behavioural change to the lane's rules — this is a content sync of rules that already run
  live, plus the keep-tree files retain pre-existing tree behaviour. The tree→live sync that
  eventually converges live is gated by #1724; this PR only lands the fold (AC4 honoured).
