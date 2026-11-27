# Change: version the planner's "waiting is a report, not an outcome" rule

## Why

Issue #3109 records a 2026-11-27 incident: several consecutive planner passes measured that the
documentation lane was inert (no DM answer, no branch, no PR) and replied with status notes —
"I'll act when gate X clears" — instead of re-dispatching a responsive lane or taking the issue
end-to-end. The owner interrupted with "Why are you fucking waiting for?!" and "make sure this
does not happen again!!!!!". The versioned skill's two-line "Idleness is the defect" rule did
not name the failure mode or the two legitimate actions, so it did not bite.

A local edit to the live profile copy at
`$HOME/.hermes/profiles/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` fixed the
behaviour on-host but left the tree stale. That is the #791 / #928 unversioned-instruction
defect: the next one-way profile sync would erase the fix. This change versions the exact text
so it can be diffed and traced to the incident.

## What Changes

- Replace the two-line paragraph in
  `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` with the incident-derived
  paragraph verbatim. It names the two actions for an inert blocking lane with an exhausted DM
  channel: re-dispatch the responsive lane that already owns the one vehicle, or take the issue
  end-to-end under the monitor contract (OpenSpec change first → worktree off `origin/main` →
  `make` gates → PR). It forbids another status note and a second PR/branch for an issue that
  already has one (#824).
- Keep the following "Check the tick itself FIRST." paragraph, the rest of the skill and the
  fleet block in `agents/llgenie-planner/SOUL.md` byte-identical.
- Add the #1123 note/index row trio and regenerate the `CHANGES.md` index row. The owner runs
  `make sync-agent-profile PROFILE=llgenie-planner` after the PR lands; this lane does not edit
  the live profile.

## Benefit

A stuck bot can no longer stall both PRs: the planner routes around the inert lane on the same
pass, and the behaviour is diffable, reviewable and traceable to the incident while tree and
live stay in sync.
