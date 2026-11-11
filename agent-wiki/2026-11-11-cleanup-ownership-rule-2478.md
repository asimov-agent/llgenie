# 2026-11-11 — cleanup-ownership-rule (issue #2478)

Closes the cleanup-ownership carrier for #1624 (cross-lane `/tmp` deletion guarantee).

- `agents/standing-rules.md` now states the rule explicitly: **cleanup names your own lane's paths,
  never a shared `/tmp` wildcard** — no prompt, script, or make target carries an `rm -rf /tmp/*`-shaped
  command; system/other-tenant `/tmp` occupants are never fleet cleanup targets.
- Criterion 1 (occupant inventory) was measured on the cron host 2026-11-11 and posted on #2478:
  53 `/tmp` occupants attributed; **0 git worktrees under `/tmp`** (all lane trees under
  `llgenie-wt/`), lane-owned entries are flat named scratch files only.
- Criterion 3 was already satisfied on-wire: #1624's `## Not covered` names #2478 (moved 2026-11-10,
  from PR #2389) and all of #1624's acceptance boxes are ticked with proven references.
- OpenSpec change `cleanup-ownership-rule` validated; scenarios use Given/When/Then.
- PR: opened from branch `fix/2478-cleanup-ownership-rule` against upstream main (closes #2478).
