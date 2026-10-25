# Tasks

- [x] 1. `openspec/changes/engine-build-dispatch` — proposal + `specs/engine-build-dispatch/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before the code
- [x] 2. `scripts/engine_image.py` — `matrix()` and the `matrix` CLI gain `--engine` / `--arch` filters (the sweep's rows are the committed params)
- [x] 3. `Makefile` — `engine-build-matrix` target (`ENGINE=`, `ARCH=`), `##` help line, `.PHONY`
- [x] 4. `.github/workflows/engine-build.yml` — `workflow_dispatch` only (engine/arch/push), guard job first, matrix from `make engine-build-matrix`, one build job per row (`max-parallel: 20`) running `make build-engine` → `make test-engine-stage`, publish only when `push=true`
- [x] 5. `tests/test_engine_build_workflow.py` — dispatch-only, guard first, matrix from the params, every row built and verified, publishing opt-in
- [x] 6. `README.md` — the workflow, the target, and the source-vs-prebuilt split (13 of 31 variants prebuilt → issue #615); dispatch table regenerated
- [x] 7. `skills/engines/llama.cpp/SKILL.md` — all four variants build from source (issue #615, first engine): the `container:` block uses the shared devel base and ships only `build/bin`; params + Dockerfiles regenerated, no prebuilt engine binary
- [x] 8. `agent-wiki/2026-10-25-engine-build-dispatch.md` — the work record, referencing issue #614
- [x] 9. Verified: `make check-workflows`, `make check-dispatch-forms`, `make check-docs`, `make check-wiring`, `make lint`, `make openspec-validate NAME=engine-build-dispatch`, and `tests/test_engine_build_workflow.py` in the test image
