# fix-engine-bump-regen-guard — Tasks

- [x] 1.1 `_regen_guard` reads `git status --porcelain`, not make stdout.
- [x] 1.2 A make `Entering directory` line does not fail the guard.
- [x] 1.3 A change to another engine's params still fails the job.
- [x] 1.4 `make test-unit` covers both cases; `make openspec-validate NAME=fix-engine-bump-regen-guard` passes.
- [x] 1.5 Commit, push, open PR against upstream main referencing #107.
- [x] 1.7 Regen writes only the bumped engine (`ENGINE=<id>`), so another engine's params are not touched.
