# A doc-named host-agent roster/count is sourced from `agents/manifest.json`, never prose (#1771)

The docs-lane skill (`agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md`,
v1.0.22) now encodes the #1768 protocol that was previously only implied: a doc that names a count or
roster of the fleet's host agents sources it from `agents/manifest.json` / `make agent-profiles-report`
at that moment — never a prose-sentence count, which is a stale census about to be true of nobody —
and a small example `agents/` tree shown under that roster is captioned as an illustrative two-of-N
sample, not the whole set.

Motivation: `docs/BOTS.md` §host-agents had said "The two **host** agents" and showed an example tree
with only two entries while `agents/manifest.json` and the tree both list 13 `llgenie-*` profiles. The
"never a prose number" rule existed in the skill but the roster-sourcing rule did not, so the "two"
defect was able to ship and needed #1768 to fix. Writing the rule next to the number rules it
complements stops the doc lane re-learning it on each audit.

Branch: `agent/issue-1771-docs-roster` from `3333200f` (live origin/main at open).
Changed: `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md` only
(version 1.0.21 → 1.0.22, one `## Pitfalls` bullet). Tree skill == live skill byte-identical
(`4fc524cd…`), so `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` is clean.
Closes #1771.
