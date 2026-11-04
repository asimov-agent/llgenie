# The profile-path change-note discipline is this lane's owned process — carried in the lane skill (#1725)

#1725 made the `agents/<profile>/` change-note discipline a first-class, owner-owned process in
`docs/BOTS.md` ("Documentation is part of the change", rule 3): a commit editing
`agents/<profile>/SOUL.md`, a lane skill under `agents/<profile>/skills/`, or `agents/manifest.json`
owes its own `agent-wiki/<stem>.md` note + `docs/changes.d/<stem>.md` row in the **same** branch
before it is ready-for-review. `check-docs` stays the strict backstop (nothing weakened); it is not
the process.

## The owner lane carries it too

This lane's `SKILL.md` (`llgenie-docs-maintainer`, "Idle / empty-queue audit") now states the
discipline as **this lane's owned process**, not just the audit's gate:

- when **this lane** changes a SOUL or lane skill, it ships the note+fragment alongside the edit in
  the same branch;
- when it audits another lane's, a missed note+fragment pair is a finding — someone else's
  implementation remains theirs, filed through the queue, never landed by the audit pass;
- `check-docs` reds a SOUL/skills edit without the pair (measured recurrence class: #1719, #1707,
  #1697 each rediscovered the gate by CI before a lane owned it), but the owned process is what keeps
  the practice current, not the red.

## Prove-the-rule

This very change edits this lane's own skill (`agents/llgenie-documentation-maintainer/skills/.../SKILL.md`,
a `NOTE_SURFACE_RES` surface) and ships this `agent-wiki/` note + its `docs/changes.d/` row + the
regenerated `CHANGES.md` row in the same branch — the discipline applies to the lane that owns it.
Implements the #1725 owned-process follow-through.
