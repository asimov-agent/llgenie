# Tasks: engine-gap-ownership-routing (issue #2270)

- [x] Add `ENGINE_DOMAIN_LABEL = "component:engine"` to `scripts/engine_skill_gap.py`:
      spawn issues carry it, label reconciliation treats a present engine label as
      `unchanged` (no POST), a repair POSTs the UNION (human labels survive), and the
      spawn report names the label set.
- [x] Lock the behaviour in `tests/test_engine_skill_gap.py`: a spawn labels
      `["bug", "agent:implement", "component:engine"]`; a pre-labelled issue is
      reported `unchanged` with zero label POSTs; a `blocked`-labelled issue keeps its
      extra label through the union repair. Battery green (`make test-unit`).
- [x] Write
      `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/engine-domain-ownership.md`:
      the two-job split (`engine-bump-plan` = existing pins,
      `render-engine-skill-gap` = new engines), the `component:engine` routing table to
      `llgenie-engine-improver`, and the #2073 gate-script negative control; link it
      from the skill's delegation walk and lock it in `tests/test_agent_skills.py`
      (`test_the_planner_carries_the_engine_domain_ownership_reference`).
- [x] Carry the engine lane's scope claim through the routing reference (the SOUL half
      of #2270 AC6 is a protected-file edit needing owner consent — filed as linked side
      issue **#2946**, which holds the drafted SOUL bullet verbatim); sync the planner
      tree to the live profile and keep `make -s check-agent-profiles` green.
- [x] Prove the two-job split dry on the live tree: `make -s engine-bump-plan` listed
      moved EXISTING pins (edge0 `bump` …) and
      `make -s spawn-engine-skill-issues DRY_RUN=1` printed `unresolved 0`
      (registry 50, skills 18, known-unsupported 32) — distinct outputs, recorded in the
      agent-wiki entry.
- [x] Create the GitHub label `component:engine` (color c2e0c6, lane description) and
      re-stamp the four closed gap issues #2902–#2905 with it; label read-back shows
      `component:engine` on all four and on #2270 itself.
- [x] `make openspec-validate NAME=engine-gap-ownership-routing` exits 0 —
      "Change 'engine-gap-ownership-routing' is valid" (rc=0, re-run fresh 2026-11-19).
- [x] Full local gates: `make lint`, `make check-wiring`, `make check-docs`,
      `make check-agent-skills`, `make check-ci-discipline`, `make test-unit` exit 0
      (unit battery: 1235 passed, 1469 subtests, UNIT_RC=0).
- [x] Three-mirror alignment verified: #2270's body Problem/Fix/Acceptance match
      proposal.md + spec.md + tasks.md, its Not covered names side issue #2946
      (read-back: `#2946` appears exactly once in the live issue body), and the
      agent-wiki entry + changes.d fragment + CHANGES.md row carry the landing trio.
