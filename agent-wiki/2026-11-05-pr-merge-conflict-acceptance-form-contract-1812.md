# pr-merge-conflict lane lands the #1796 acceptance-criteria form contract (#791 / #1812)

The #791 per-lane acceptance-criteria form-contract fleet rollout requires every
affected lane's skill to state the contract verbatim. This lane's
`SKILL.md` on main at `dde5c9ec` did not yet carry it, which is the #1796 #1
gap the reviewer's #1804 verdict left unticked (6/6 gate).

## Change

`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md` — a new
Hard-rules bullet states the form contract verbatim: **every issue this lane
files AND every PR body it opens carries a `## Acceptance criteria` section with
each criterion a `- [ ]` markdown checkbox, one per provable outcome; a
criterion a reviewer cannot tick is not one (#745)**, citing #791/#1796/#1812.

- **Text-only** — no scripts, tests, or workflows altered; the change note is
  the `docs/changes.d/` pair plus this `agent-wiki/` entry (#1123).
- **OpenSpec presence** — `openspec/changes/acceptance-form-contract-pr-merge-conflict/`
  (proposal + spec + tasks all `[x]`) per the #1810 presence gate.
- **#1812** — PR closes the dispatch umbrella issue.
