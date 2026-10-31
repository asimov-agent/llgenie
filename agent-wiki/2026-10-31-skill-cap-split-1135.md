# Split the two over-cap agent SKILL.md files into reference + pointer

Fixes #1135's two remaining tree rows: `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`
and `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md` were both at/over
`skill_manage`'s ~100,000-character cap, so the lanes could no longer accept a patch — the save
was refused and the whole batch rolled back, silently. Both are now split by the established
extract-and-point pattern (the same one the planner's own earlier split used, the first row of
#1135's measured table): the largest self-contained section was moved **verbatim** to a
`references/` file, the SKILL.md keeps the `##` heading and replaces the body with a one-line
pointer, and each file is back under the cap with room for a next lesson.

## What changed

- `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`
  - 100,107 b → **87,355 b** (under ~90k)
  - `## One builder per file, and prove no duplicate before you dispatch` → `references/one-builder-per-file.md`
  - `## Pitfalls` → `references/pitfalls.md`
- `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md`
  - 100,742 b → **70,214 b** (under ~90k)
  - `## Hard rules` → `references/hard-rules.md`

Measured at the branch head on `origin/main` = `d9c186cd` (both files re-measured at that sha
before the split: 100,107 and 100,742).

## Verbatim proof

Each moved section is byte-identical to its source: the reference file's section body equals the
section body read out of the `HEAD` blob (`git show HEAD:<file>`), and every line of the moved
body appears in the reference (0 lines lost). The `point_sections.py` repoint step asserted the
removed body equals the reference body before allowing the edit. No paraphrase, no renumbering —
the `##` headings are retained in SKILL.md so internal anchors keep resolving.

## Not covered

The host-side, not-yet-versioned `llgenie-pr-reviever` profile's
`skills/software-development/llgenie-pr-review/SKILL.md` is still over-capped (live-only); it is
chased as its own follow-up on #1135, not in this PR.
