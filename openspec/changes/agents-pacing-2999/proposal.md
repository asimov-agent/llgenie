# Proposal: agents-pacing-2999

## Why
AGENTS.md's "Host-side task pacing" already tells the agent to move to the next issue while a lane's CI runs, but it does not forbid the idle shape that keeps happening: after pushing a lane, the agent re-polls the watcher and holds the board until the CI verdict lands (measured 2026-11-21 after PR #2998 was pushed). The owner restated the behaviour as a standing mandate: "work on the nxxt issue/PR while waiting for ci pipeline, must be part of your agents.md behavior" (issue #2999).

## What Changes
- Add one explicit pacing rule to `AGENTS.md` → "Host-side task pacing (MANDATORY, durable)": a lane whose CI is in flight is DONE for scheduling purposes — the agent starts the next board issue immediately (fresh worktree, OpenSpec change first), and every CI re-poll happens only inside the background watcher task, never as the agent's foreground activity.
- Name the forbidden shapes: idle sleep/poll chains between a push and the next lane's start; treating a pending CI verdict as a reason to hold the board.
- No code, no workflow changes: this is a governance-text change to AGENTS.md, verified by the docs gates.

## Impact
- Affected capability: `host-agent-pacing` (behavioral pacing of the host agent).
- Affected file: `AGENTS.md`.
- Gates that read it: `make check-docs`, `make lane-preflight`.
