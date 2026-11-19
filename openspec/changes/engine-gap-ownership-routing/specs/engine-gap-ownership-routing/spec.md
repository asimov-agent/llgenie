# Spec Delta: engine-gap-ownership-routing (issue #2270)

Capability: `engine-gap-ownership-routing`
Issue: [#2270](https://github.com/asimov-agent/llgenie/issues/2270)

## ADDED Requirements

### Requirement: a spawned engine-gap issue carries the engine-domain label

`scripts/engine_skill_gap.py` SHALL label every engine-gap tracking issue it creates
(or repairs a label on) with `ENGINE_DOMAIN_LABEL = "component:engine"`, in addition to
its existing `bug` + queue labels, set through the REST label endpoint and read back
(#724 discipline). The queue label `agent:implement` SHALL stay: the issue must remain
claimable by bots, and the domain label is what pins WHICH lane owns it. An existing
issue that already carries the domain label SHALL not be re-labelled or counted as a
drift.

#### Scenario: a spawn carries bug, queue, and engine labels

- **Given** a fixture issue store with no labels on issue 1
- **When** `spawn_issue` runs for engine `strata` with kind `skill_gap`
- **Then** the issue's labels are exactly `["bug", "agent:implement", "component:engine"]`
  (sorted) and the call set them via the REST endpoint
- **Test:** `tests/test_engine_skill_gap.py::test_a_spawned_gap_issue_carries_the_engine_domain_label`

#### Scenario: repairing a missing engine label is idempotent

- **Given** an open issue that already carries `component:engine`
- **When** the spawn leg reconciles labels on it
- **Then** it reports `unchanged` and issues no label POST
- **Test:** `tests/test_engine_skill_gap.py::test_an_issue_with_the_engine_label_is_reported_unchanged`

### Requirement: the planner delegation walk names the engine domain first

`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/` SHALL carry an
`engine-domain-ownership.md` reference that (a) states the two-job split —
`make engine-bump-plan` moves pins of EXISTING pinned engines,
`make render-engine-skill-gap` discovers NEW engines and spawns their tracking issues,
proving the bump workflow never collects new engines — (b) routes every
`component:engine` work item (spawned gap, engine-bump PR repair, engine pin/gate red)
to `llgenie-engine-improver`, and (c) keeps the #2073 negative control beside it: a
gate-SCRIPT defect in engine-bump stays with `llgenie-ci-pipelines-maintainer`.
`SKILL.md` SHALL link the reference from its delegation walk.

#### Scenario: the reference states discovery-vs-bump and routes by domain

- **Given** the shipped reference file
- **When** it is read
- **Then** it names both make targets and which one owns new-engine discovery, names
  `component:engine` as the routing key, names `llgenie-engine-improver` as the owner,
  and states the gate-script negative control in the same table
- **Test:** `tests/test_agent_skills.py::test_the_planner_carries_the_engine_domain_ownership_reference`

### Requirement: the engine-improver lane's scope claim reaches the gap work

`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/engine-domain-ownership.md`
SHALL name new-engine scaffold/params work and engine-bump PR repair as in-scope duties
of `llgenie-engine-improver`, so the routing table itself states the claim. The SOUL-text
half of issue #2270's AC6 ("the SOUL **and/or** the reference") is filed as linked side
issue #2946: `agents/llgenie-engine-improver/SOUL.md` is a protected agent-instruction
file whose edit needs owner consent (consent prompts timed out 2026-11-19). The
requirement is met through the reference.

#### Scenario: the reference states the lane's gap duties

- **Given** the shipped reference file
- **When** its routing table is read
- **Then** the spawned-gap row dispatches `component:engine` gap issues to
  `llgenie-engine-improver` and names the duty (scaffold, pinned params, matrix row,
  verify rebuild), while the gate-SCRIPT row stays with `llgenie-ci-pipelines-maintainer`
- **Test:** `tests/test_agent_skills.py::test_the_planner_carries_the_engine_domain_ownership_reference`
