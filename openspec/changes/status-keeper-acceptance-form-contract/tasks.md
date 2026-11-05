# status-keeper-acceptance-form-contract — Tasks

Issue: [#1812](https://github.com/asimov-agent/llgenie/issues/1812)

- [x] 1. `agents/llgenie-status-keeper/skills/llgenie-status-keeper/SKILL.md` folded live→tree byte-identical (v1.1.0 → tree) then bumped 1.1.0 → 1.2.0 with the `## Acceptance-criteria form contract (#1796 #1)` section stating the contract verbatim (#1796 #1).
- [x] 2. Change-note trio (#1123) shipped for this PR: `agent-wiki/2026-11-05-status-keeper-acceptance-form-contract-1812.md` + `docs/changes.d/2026-11-05-status-keeper-acceptance-form-contract-1812.md` + `CHANGES.md` regen.
- [x] 3. `make check-docs` and `make lint` green; openspec change (this dir) present with proposal/spec/tasks so the #1810 openspec-presence gate is satisfied for the `agents/` path.
- [x] 4. Versioned via #791 with the SYNC line (`make sync-agent-profile PROFILE=llgenie-status-keeper`) per #1724; PR links #1812.
- [x] 5. No edit to `issue_body.py`, `acceptance_writeback`, or `auto-merge.yml` (#1644/#1088/#491).
