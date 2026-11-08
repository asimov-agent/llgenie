# Tasks — skill-size-cap-gate

- [x] Add `SKILL_MAX_CHARS = 100_000` and the `skill-size` finding to `scripts/check_agent_profiles.py::_skill_findings`, naming the file, the overflow and the remedy.
- [x] Add `skill_size_exceptions` / `_stale_exemption_findings` and the `skill-size-exemptions` / `skill-size-exemption-stale` keys; print exempted files in `agent-profiles-report`.
- [x] Record the three pre-existing over-limit skills as dated exemptions naming issue #2114 in `tests/fixtures/skill-size-exceptions.json`.
- [x] Add the four tests (over-limit red + remedy, exemption honoured, stale exemption, entry with no issue) to `tests/test_agent_profiles.py`; the module passes 149/149.
- [x] Prove the gate by negative control: the pre-change body reports `FAIL skill-size … 1,977 over … move sections into references/`, the slim body reports OK.
- [x] Slim `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md` tree-based: `## When to Use` moved verbatim to `references/when-to-use-and-pass-shape.md`, body 102,432 b → 97,962 b.
- [x] Commit the five references (`when-to-use-and-pass-shape`, `orchestrator-tick-contract`, `pass-contract-and-sweep`, `host-lane-precedence-over-ci`, `lane-gap-audit`, `fleet-quiet-diagnosis`) and link them from the pointer block.
- [x] Record the change: `agent-wiki/2026-11-08-orchestration-skill-size-2084.md` + `docs/changes.d/` row + `make changes-index`.
- [x] `make lane-preflight` → `preflight: OK (6 gate(s))`; `make openspec-validate NAME=skill-size-cap-gate` passes.
