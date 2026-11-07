# Fold the docs-maintainer live profile back into the tree (provisioning seam, #2019)

## Why

The docs-maintainer live profile and the committed tree under `agents/llgenie-documentation-maintainer/`
must agree so the provisioning seam (#791/#1060/#1724) stays clean: the tree is the source the next
provisioning reads, and `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` reds
whenever live and tree differ.

An own-domain audit (tracked #1645, finding #2019) measured live→tree drift on the lane's own skill:
`SKILL.md` is one version ahead live (v1.0.23, 99414 b) than the tree (v1.0.22, 101849 b), 6
`references/` files are live-longer than the tree (agents-soul-doc-changes, base-race-rebase-and-metadata,
dispatch-race-verification, lint-and-gates, merged-ci-verification, own-domain-audit), and 4 reference
files are live-only, never committed (acceptance-writeback-heading, acceptance-writeback,
acceptance-writeback-seam, landed-change-verification). Re-measured at `origin/main` `6cec9d8d` — #2014
moved main but touched only `docs/ARCHITECTURE.md`, so the skill drift is unchanged.

## What Changes

- Fold the 10 drifted files live→tree VERBATIM (the live profile is the richer, newer copy; #791
  drop-rule conservation refused to overwrite it with the older tree copy — the TREE is fixed, never
  the live profile shrunk). Live refs 23 = tree 23 after the fold.
- Regenerate `CHANGES.md` from fragments (`make changes-index`) so the fold change-note trio lands
  without a hand-edit of the rendered index.
- No product code, scripts, tests or workflows change; the fold is documentation of the docs-maintainer
  profile live behaviour into the committed tree.

## Benefit

`make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` reports no diff for the 10
folded files (tree == live), the provisioning seam is clean, and the next sync has nothing to
conserve-overwrite.

## Not covered

- Live profile files for OTHER lanes remain that lane's own fold finding (#1060 per-lane discipline).
- The lane's `SOUL.md` drift was tree-ahead (2 fleet rules #1891/#1889 the live profile predated) —
  resolved by a normal tree→live provisioning sync, not a live→tree fold.
- New docs work and any other issue are out of this PR scope.

## Technical

- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md`
- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/{agents-soul-doc-changes,base-race-rebase-and-metadata,dispatch-race-verification,lint-and-gates,merged-ci-verification,own-domain-audit}.md` (6 live-longer)
- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/{acceptance-writeback,acceptance-writeback-heading,acceptance-writeback-seam,landed-change-verification}.md` (4 live-only new)
- change-note trio: `agent-wiki/2026-11-07-docs-maintainer-2019-skill-fold.md`, `docs/changes.d/2026-11-07-docs-maintainer-2019-skill-fold.md`, `CHANGES.md` (regenerated, 626→627)
- measured at `origin/main` `6cec9d8d`; gate: `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1`
