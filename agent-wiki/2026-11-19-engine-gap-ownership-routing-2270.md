# 2026-11-19 — engine-gap ownership routing (#2270, #2946)

OpenSpec change: `engine-gap-ownership-routing`.

## What was verified against the spec

- **Spawn labelling** (`scripts/engine_skill_gap.py`): `ENGINE_DOMAIN_LABEL =
  "component:engine"` added to the spawn triple `SPAWN_LABELS = [bug, agent:implement,
  component:engine]`; reconciliation POSTs the UNION of existing + spawn labels (human
  labels like `blocked` survive), reports `unchanged` (no POST) when the triple is
  already present, and the spawn report names the label set. Verified by
  `tests/test_engine_skill_gap.py` (81 green incl. the two new tests
  `test_a_spawned_gap_issue_carries_the_engine_domain_label` and
  `test_an_issue_with_the_engine_label_is_reported_unchanged`).
- **Planner routing table**: new reference
  `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/engine-domain-ownership.md`
  states the two-job split and routes `component:engine` work to
  `llgenie-engine-improver`, with the #2073 gate-SCRIPT negative control adjacent.
  Locked by `tests/test_agent_skills.py::test_the_planner_carries_the_engine_domain_ownership_reference`;
  linked from the skill's delegation walk.
- **Two-job split dry proof** (live tree, main `cbead8b698`): `make -s engine-bump-plan`
  listed moved EXISTING pins (edge0 `old 4a7964de… → new 8a2eb4d4…`, status `bump`), and
  `make -s spawn-engine-skill-issues DRY_RUN=1` printed `no unresolved engine (registry
  50 engines, 18 skills … unresolved 0)` — distinct outputs proving the bump workflow
  does not collect new engines.
- **On-wire labels**: GitHub label `component:engine` created (color c2e0c6, engine-lane
  description); closed gap issues #2902–#2905 and #2270 re-stamped; read-back shows
  `component:engine` on all five.

## Key decisions

- `agent:implement` STAYS on gap issues (they remain bot-claimable); the domain label is
  the routing key the planner reads — routing became a field read, not a re-derivation.
- The SOUL-text half of #2270 AC6 ("the SOUL **and/or** the reference") could not be
  landed here: `agents/llgenie-engine-improver/SOUL.md` is a protected agent-instruction
  file and both consent prompts timed out. Filed as side issue **#2946**, which carries
  the drafted SOUL bullet verbatim and is labelled `blocked` + `component:engine`.
  The OpenSpec change was re-scoped FIRST (spec requirement 3 rewritten to the
  reference-carried claim) so code, spec and issue never contradict each other.

## Current status

Implementation + docs + on-wire label work complete on branch
`feat/engine-gap-ownership-routing`; gates and PR tracked in the change's `tasks.md`.
#2946 awaits owner consent for the protected-file edit.
