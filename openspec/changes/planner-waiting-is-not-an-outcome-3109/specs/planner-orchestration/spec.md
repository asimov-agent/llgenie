# Spec: planner orchestration liveness

## ADDED Requirements

### Requirement: an inert lane with an exhausted DM channel is a routing condition

The versioned planner skill SHALL state that a status note reciting a gate ("I'll act when gate
X clears"), repeated while a blocking lane is inert, is a report and never an outcome. When a
blocking lane is inert — no DM answer, no branch, no PR — and its DM channel is exhausted, the
planner SHALL NOT keep posting status; it SHALL either re-dispatch the responsive lane that
already owns the one vehicle for that issue to finish it on its own branch, or take the issue
end-to-end under the monitor contract (OpenSpec change first → worktree off `origin/main` →
`make` gates → PR).

#### Scenario: blocking lane never answers

- **Given** a blocking lane has not answered across DMs and has no branch or PR,
- **when** the planner reaches that gate on a pass,
- **then** it re-dispatches the responsive owner of the one existing vehicle, or takes the
  issue end-to-end, on that same pass — it does not post another "waiting on gate X" note.

#### Scenario: no second vehicle

- **Given** an issue already has one branch/PR,
- **when** the planner takes over that issue under the monitor contract,
- **then** it finishes or extends the existing vehicle; it never opens a second PR or branch
  (#824), and a bounced DM / "never answered within the wait ... do not resend" is treated as a
  routing signal rather than a stop condition.

### Requirement: the sharpened rule stays inside the orchestration skill

The change SHALL leave the following "Check the tick itself FIRST." paragraph, the rest of
`agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`, and the fleet block in
`agents/llgenie-planner/SOUL.md` byte-identical; no gate, workflow or standing-rule file SHALL
change.

#### Scenario: drift gates after the edit

- **Given** the edited versioned skill at the PR head,
- **when** `make -s check-docs`, `make -s skills-validate` and the fleet-block check run,
- **then** they exit 0 and `git diff origin/main HEAD -- agents/llgenie-planner/SOUL.md` is empty.
