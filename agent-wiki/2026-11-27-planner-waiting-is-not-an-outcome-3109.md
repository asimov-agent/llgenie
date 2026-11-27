# Planner: waiting is a report, never an outcome (issue #3109)

PR on branch `agent/issue-3109-planner-skill-versioning`, cut from freshly fetched
`origin/main@892632d806a796ed02299c33f47ac42ba5483b96`.

## What changed

- `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` now carries the
  incident-derived paragraph verbatim from the on-host fix that closed the 2026-11-27
  stall. The old two-line "Idleness is the defect" rule did not name the failure mode:
  a planner that keeps posting "I'll act when gate X clears" while a blocking lane
  is inert is indistinguishable from refusing to work.
- The sharpened rule names the two legitimate actions when a blocking lane is inert
  and its DM channel is exhausted: re-dispatch the responsive lane that already owns
  the one vehicle for the issue, or take the issue end-to-end under the monitor
  contract (OpenSpec change first → worktree off `origin/main` → `make` gates → PR).
  It also forbids opening a second PR/branch for an issue that already has one
  (the #824 failure) and treats a bounced DM / "never answered within the wait ... do
  not resend" as a routing signal, not a stop condition.
- The following "Check the tick itself FIRST." paragraph, the rest of the skill, and
  the fleet block in `agents/llgenie-planner/SOUL.md` are byte-identical to their
  pre-change versions.

## Why it is versioned

A local edit to the live profile copy at
`$HOME/.hermes/profiles/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`
fixed the behaviour on-host but left the tree stale, so the next profile sync would
have erased it (#791 / #928). The exact text now lives in the repository; the owner
runs `make sync-agent-profile PROFILE=llgenie-planner` after this PR lands. This lane
does not edit the live profile.

## Key decisions

- Behaviour sharpening inside the orchestration skill only: no SOUL.md, gate,
  workflow, standing-rule or other lane's file was touched.
- The note and one-row `docs/changes.d` fragment are the #1123 companions for the
  behavioural change; the `CHANGES.md` index row is regenerated with
  `make changes-index`.
- No self-tick (#1644), no hand-merge (#1088), no arm and no second vehicle.
