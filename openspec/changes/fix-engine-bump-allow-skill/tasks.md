# fix-engine-bump-allow-skill — Tasks

- [x] 1.1 `_regen_guard` allows `skills/engines/<id>/SKILL.md` for the bumped engine.
- [x] 1.2 A change to another engine's file, including its SKILL.md, still fails the job.
- [x] 1.3 `make openspec-validate NAME=fix-engine-bump-allow-skill` passes.
- [x] 1.4 Commit, push, open PR against upstream main referencing #127.
- [x] 1.5 Re-dispatch `engine-bump` after merge and confirm a bump job gets past the guard.
