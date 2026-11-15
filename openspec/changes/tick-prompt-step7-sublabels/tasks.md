## 1. Renumber STEP 7 sub-items

- [x] 1.1 In `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`, renumber STEP 7's sub-items `6a`->`7a`, `6b`->`7b`, `6d`->`7c`; STEP 6 unchanged.
- [x] 1.2 Update the report-template cross-reference `(step 6b)` -> `(step 7b)`.

## 2. Prove the fold precondition (#791 truncation trap)

- [x] 2.1 Measure the two formerly `live-edited-not-tree` planner prompts tree<->live at this head and record the numbers in the note.

## 3. Notes + gates

- [x] 3.1 Add `agent-wiki/2026-11-15-tick-prompt-step7-sublabels-2666.md` + `docs/changes.d/` row + `make changes-index`.
- [x] 3.2 `make -s check-docs` rc 0; `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` byte-identical; `make openspec-validate` passes.
