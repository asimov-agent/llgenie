# Documentation-maintainer live skill drift fold

## What changed

The documentation-maintainer lane's live `skills/llgenie-docs-maintainer/SKILL.md` had grown
**+991 b** (71,239 vs 70,248) since the last versioning fold (#1279), carrying a live-only lesson
produced by the 2026-11-01 own-domain audit: **run the audit in a fresh scratch worktree at
`refs/remotes/origin/main`, never the repo's main checkout** (a local `main` branch can sit many
merges behind and `docs_audit.py` then measures an old tree, reporting "no usable referent" and
lower counts that read as defects), and **prove change-note coverage with `make -s check-docs`, not
by globbing `docs/changes.d/*<pr-number>*`** (fragments are named by note stem or issue, so a
PR-number glob returns 0 for a present note). Live is source of truth; the tree catches up
byte-identically (#791).

## Files

- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md` — live→tree
  byte-identical fold (71,239 b). `SOUL.md` unchanged (already aligned, 16,175 b).
- `CHANGES.md` — re-rendered by `make changes-index` (this issue's row).
