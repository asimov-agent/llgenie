# planner-cron-store — delta

## ADDED Requirements

### Requirement: Restored planner cron jobs carry pinned ids and versioned prompts
When a planner-profile cron store is found emptied after a Hermes-side store
loss, every expected scheduled job SHALL be re-created in the live store with
its original pinned job id and a prompt byte-identical to its versioned copy
under `agents/llgenie-planner/prompts/` (modulo the single framing trailing
newline the gates already normalize). A restored job SHALL mirror the live
conventions of its cohort (schedule, deliver, skills, toolsets).

#### Scenario: Tick job reappears against its pinned id
- **WHEN** `make check-tick-prompt` runs on the host after the store restore
- **THEN** it exits 0 ("live prompt == versioned") rather than 2 ("job
  cc5d2bd4083a not found")

#### Scenario: No prompt drift after restore
- **WHEN** `make check-cron-drift` runs after all expected jobs are restored
- **THEN** it exits 0 with every live job prompt byte-identical to its
  committed prompt file

### Requirement: A restored scheduled job must prove a live dispatch
A restored cron job SHALL be proven live by a durable execution row: one armed
run whose run id is readable from `hermes cron runs <job-id>` before the
restore is declared done.

#### Scenario: Tick dispatch has a durable run id
- **WHEN** `hermes cron runs cc5d2bd4083a` is read after arming one run
- **THEN** a run with a distinct run id and terminal status appears in the
  durable execution history

### Requirement: Cron store losses are root-caused with evidence timestamps
When a profile cron store is found wiped, the incident record in `agent-wiki/`
SHALL name the measured timestamps (last healthy save, wipe stamp, mtime), the
document shape proving which writer persisted it, and why the platform's own
restore net did not fire.

#### Scenario: Wiki names the mechanism, not just the symptom
- **WHEN** the incident entry is reviewed
- **THEN** it carries the update-run receipts, the drain/hard-interrupt log
  lines, the empty-document stamp, and the load-coercion mechanism as separate
  measured evidence lines
