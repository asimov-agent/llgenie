# Tasks: planner-live-parity-2479

- [x] Diff all 48 differing planner-profile files live↔tree and record the per-file resolution (tree kept + reason, live kept, or merged)
- [x] Verify the two #2479-named SKILL.md files are byte-identical (folded verbatim by PR #2391) with cmp evidence
- [x] Run `make sync-agent-profile PROFILE=llgenie-planner` from the fixing head, then `CHECK=1` → 0 differences; record the run on #2479
- [x] Record the resolution table in `agent-wiki/` + `docs/changes.d/` + CHANGES.md row
- [x] `make openspec-validate NAME=planner-live-parity-2479` passes and the ticked checklist lands with the PR
