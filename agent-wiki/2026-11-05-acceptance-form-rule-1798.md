# Universal acceptance-criteria form rule versioned in-tree (#1798)

The planner lane's live reference `llgenie-bot-orchestration/references/acceptance-form-rule.md`
was updated (live profile, this session) to add the hand-authored-bold-heading consequence of the
#1796 universal form rule: a bold `**Acceptance criteria:**` section (no `## ` heading) defeats both
the gate read (`issue_body.section_body` parses zero criteria, gate returns green) and the #1644 tick
seam (`acceptance_writeback.tick_acceptance` raises `BodyError`), so a reviewer verdict can never tick
that issue — measured on the wire for #1792.

This commit folds that updated live reference into the tree **byte-identically**
(`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/acceptance-form-rule.md`, blob
`7808b1a9`, 2967 bytes, == current live) per the lane's #791/#1777 versioning rule: a skill change
under this profile arrives as an issue plus a PR that commits the text under `agents/llgenie-planner/`.
Without it the change is a silent private edit — not diffable, not reviewable, not traceable to #1792.

Docs/skill-text-only: no scripts, tests, or workflows altered.
