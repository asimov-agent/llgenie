## ADDED Requirements

### Requirement: A pushed lane with CI in flight never idles the host agent
The host agent's pacing rules SHALL state that a lane whose CI pipeline is still running is DONE for scheduling purposes: after pushing a lane, the agent MUST immediately start the next board issue (fresh worktree, OpenSpec change first) instead of waiting for that lane's CI verdict, and all CI re-polling MUST live in the background watcher task rather than in the agent's foreground activity.

#### Scenario: CI in flight while the board has work
- **WHEN** a lane has been pushed and its CI run has not concluded
- **AND** the board has at least one unclaimed issue
- **THEN** the agent is working the next issue in its own fresh worktree
- **AND** the previous lane's status is observed only through its background watcher

#### Scenario: Idle polling is a pacing violation
- **WHEN** an agent turn between two lane starts consists only of sleep/poll chains on a pending CI
- **THEN** that behaviour violates the pacing section of AGENTS.md, and the watcher task is the only sanctioned re-poll
