# Tasks — planner-propagation-hub

- [ ] 1. Add the "The planner is the propagation hub" section to
      `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` mirroring issue #1194's three
      numbered points and the on-record / no-re-dispatch disposition, in the planner's own voice.
- [ ] 2. `docs/changes.d/planner-propagation-hub.md` + `agent-wiki/2026-10-31-planner-propagation-hub.md`
      reference #1194.
- [ ] 3. `make openspec-validate NAME=planner-propagation-hub` exits 0.
- [ ] 4. `make lane-preflight` passes (fast gates green) at the would-be-pushed head.
- [ ] 5. Scoped `ci-unit` gates (`check-agent-profiles`, `check-docs`, `check-wiring`, the unit suite) green.
