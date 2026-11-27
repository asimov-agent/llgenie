# Tasks — planner waiting is not an outcome (#3109)

- [x] Replace the two-line "Idleness is the defect" paragraph in `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` with the incident-derived paragraph verbatim from issue #3109.
- [x] Keep the "Check the tick itself FIRST." paragraph, the rest of the skill and `agents/llgenie-planner/SOUL.md`'s fleet block byte-identical.
- [x] Add `agent-wiki/2026-11-27-planner-waiting-is-not-an-outcome-3109.md`, its one-row `docs/changes.d/` fragment and the regenerated `CHANGES.md` index row (#1123).
- [x] `make openspec-validate NAME=planner-waiting-is-not-an-outcome-3109` and `make -s check-docs` exit 0 at the PR head.
- [x] PR body carries `AGENTS:`, `BASE:` and `SYNC:` stamps and the allowlisted commit author; no self-tick, no hand-merge, no arm.
