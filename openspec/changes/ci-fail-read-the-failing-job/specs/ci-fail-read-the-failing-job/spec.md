# CI-fail read-the-failing-job

## ADDED Requirements

### Requirement: the implementer lane's skill codifies the failing-job-log-first sequence

The implementer lane's versioned skill
(`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`)
states the mandatory sequence on a red bot-gate: read the failing job's OWN log and quote the
failing step + `[step] FAILED` line + Makefile target + run id at the real head BEFORE any fix
dispatch or any green/red/reviewable claim, and attribute the root cause to THAT gate via the
gate→defect map.

#### Scenario: a red bot-gate is read before any claim or dispatch

Given a PR whose CI shows a red gate
When a lane prepares to dispatch a fix, or to report green/red/reviewable,
Then the lane first reads the failing job's own log with
`gh api .../actions/jobs/<job-id>/logs --allow-escape-sequences`
And quotes the exact failing step + `[step] FAILED` line + Makefile target + run id at the real head.
And attributes the root cause to that gate via the gate→defect map (#792 AGENTS, #845 base,
#1724 SYNC, #1329 closing, #858/#843 cancelled).

#### Scenario: green is reported only off a concluded run

Given a lane reporting a PR "green"
When the report is composed
Then it cites the completed run id + head sha of the concluding run
And it is not green while any `linux/*` or guard/scope row is `in_progress` or `cancelled`.

#### Scenario: an unretrievable log is not given a fabricated cause

Given a red gate whose job log the endpoint refuses mid-run ("run is still in progress" / BlobNotFound)
When a lane must report the cause
Then it says exactly "error line not yet retrievable — unlocks at run completion"
And it does not invent a cause, and does not pronounce the PR reviewable or merged.

### Requirement: the change is text-only under the lane dir, with the change-note trio

The change stays text-only under `agents/llgenie-issse-implementer/` plus the openspec change dir
and the change-note trio; no scripts, tests, or workflows alter CI behaviour.

#### Scenario: the pointer is present

Given the change adds the reference under `agents/llgenie-issse-implementer/skills/`
When the SKILL.md is read
Then it carries a pointer to `references/red-bot-gate-read-the-failing-job-log.md`.
