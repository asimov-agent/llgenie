# Lane-role audit committed as a reusable planner reference (#1777)

The planner's fleet-integrity meta-audit is now a maintained reference under its own skill tree:
`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/lane-role-audit.md` (byte-identical
to the planner's live profile copy, 24 lines), with a one-line pointer added to that skill's
`SKILL.md` header block.

The procedure, previously tribal knowledge from one pass (owner request 2026-11-05), is now a diffable
step list: enumerate lanes from `agents/` (SET-subset, never equality on a prose list); presence gate
(SOUL.md + ≥1 skills/<n>/SKILL.md per lane); role-split overlap/gap via `agents/manifest.json`
`profiles[].rules` + cross-referenced SOUL deferrals; the recurring operational-lane idle-audit-encoding
grep with exact vocabulary and hit-count reporting; file one refined six-section issue PER gap labeled
`continuous-improvement` + `agent:refined`; route to the OWNING lane on-issue + DM, never
self-implement. Measured at `0dcbda8a`: four lanes (security, engine-improver, pr-reviever,
rebase-conflicts / pr-merge-conflict) scored 0 on the idle-audit-encoding grep — the gap the reference
makes repeatable.

Branch: `agent/issue-1777-lane-role-audit` from `3333200f` (live origin/main at open). Changed:
the new reference file + SKILL.md pointer only (docs lane `agents/llgenie-planner/`, no data/scripts/
workflows). Closes #1777.
