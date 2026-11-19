# Proposal: route spawned engine-skill-gap work to the engine lane

## Why

Issue #2270 measures a routing gap: `scripts/engine_skill_gap.py` spawns one tracking
issue per new/unresolved engine but labels it with the generic `QUEUE_LABEL =
"agent:implement"`, which selects the implementer lane. The engine-domain job those
issues represent (scaffold the skill, derive build params, verify the rebuild on
Linux) belongs to `llgenie-engine-improver` — the lane whose profile names
trending-engine sync and serving params. The planner already documents the
discovery-vs-bump ownership split (`domain-ownership-dispatch.md`) and routes engine
issues by domain (`gh-issue-to-kanban-triage.md`, `host-lane-precedence.md`), but the
spawned issue itself carries no domain marker, so routing must be re-derived by every
reader and was measured being got wrong (#2903/#2904 were spawned engine-gap issues
that closed through the implementer queue).

## What Changes

- `engine_skill_gap.py` labels every spawned (or repaired) engine-gap issue with a
  domain label `component:engine` in addition to `bug` + `agent:implement` — set
  through the REST label endpoint and read back, same #724 discipline as the queue
  label. The queue label stays: the issue must remain visible to bots; the domain
  label is what pins WHICH lane owns it.
- The planner's delegation walk gains an explicit engine-domain row: a spawned
  engine-gap issue (`component:engine`), an engine-bump PR needing repair, and
  engine pin/gate reds dispatch to `llgenie-engine-improver`; a gate-SCRIPT defect in
  engine-bump stays with `llgenie-ci-pipelines-maintainer` (the #2073 two-trails
  negative control, stated in the same reference so both rows are adjacent).
- The engine lane's scope claim rides the routing reference: it names new-engine
  scaffold/params and engine-bump PR repair as `llgenie-engine-improver` duties. The
  SOUL-text half of #2270 AC6 ("the SOUL **and/or** the reference") is a protected-file
  edit needing owner consent; it is filed as linked side issue #2946 and satisfied here
  through the reference.
- The two-job split (`make engine-bump-plan` = which existing pins moved vs
  `make render-engine-skill-gap` = which engines are NEW) is exercised dry in the
  change record, proving the bump workflow does not collect new engines.

## Impact

- Affected specs: `bots-automation` (engine gap spawn labelling),
  `agent-orchestration` (engine-domain delegation row)
- Affected code: `scripts/engine_skill_gap.py`, `tests/test_engine_skill_gap.py`,
  `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/`,
  `tests/test_agent_skills.py`
- New GitHub label `component:engine` (created via the label API; no repo gate
  enumerates labels)
- Out of scope, side issue #2946: the `llgenie-engine-improver` SOUL duty claim
  (protected agent-instruction file; owner consent gate)
