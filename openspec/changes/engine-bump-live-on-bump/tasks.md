# Tasks

- [x] 1. OpenSpec change: `proposal.md`, `specs/engine-bump-live-on-bump/spec.md`, this checklist
- [x] 2. Remove `make test-engine-bump-live` from the `pipeline.yml` unit job
- [x] 3. `engine-bump.yml`: after the new pin and the documentation review, and before the PR, the TensorFold row sets up Docker, runs `make test-env`, then `make test-engine-bump-live`; the job has `packages: read`
- [x] 4. `tests/test_engine_bump.py` locks the absence on the unit job and the order on the bump job
- [x] 5. Docs: `docs/BOTS.md`, `docs/ARCHITECTURE.md`
- [x] 6. `agent-wiki/2026-10-29-engine-bump-live-on-bump.md` and `docs/changes.d/2026-10-29-engine-bump-live-on-bump.md`, then `make changes-index`
- [x] 7. Gates: the touched unit tests, `make openspec-validate NAME=engine-bump-live-on-bump`, `make check-workflows`, `make check-docs`
