# Rebase lane: dirty-watch lessons must land as tree PR, never live-profile patches

Issue #1156 (filed by this lane, measured at main `a653cdc9`) — the `llgenie-dirty-watch` cron was
appending skill lessons directly into the **live** `~/.hermes/profiles/llgenie-pr-merge-conflict/skills/**`,
patching both colliding skill copies. Because `make sync-agent-profile` is one-way (tree → live), a
live-only write can never return to the tree: the cron **re-created `live-longer` drift after every PR
that cleared it**, so this lane's live→tree debt could never reach a durable zero. Measured: drift
cleared by #1147 at 07:57Z, re-created by the cron at 08:40:37Z (live `references/pitfalls.md` 17391 →
19096 b).

Repo-side change (this PR, `closes #1156`):

- **SKILL.md**: added the write-target rule — skill lessons, including anything this lane's write/watch
  cron emits, land **only by issue + PR under `agents/llgenie-pr-merge-conflict/`**, never as a
  live-profile patch; a lesson written to the live profile is *profile-only, tree PR still owed*.
- **`references/skill-script-hygiene.md`**: rewrote the "two skill copies" section and removed the
  "mirror canonical → served" corollary — there is **ONE canonical copy, in the tree**; a second live
  copy is drift to clear, never a second artifact to keep patching (removing the instruction that
  regenerated the `skills/development/llgenie-pr-rebase/` duplicate).
- **`tests/test_agent_profiles.py`**: added a behaviour test pinning that a live-only write to a skill's
  `references/*.md` (the cron's own path class) fires `live-longer` and `live-edited-not-tree` — the
  drift gate already reports the shape, and now it is proved against the cron's exact path.

The host cron job `244a75ddc597`'s prompt is updated by the planner only after this merges. This PR
does not edit the cron itself.
