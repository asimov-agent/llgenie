# Tasks — engine-skill-tensorfold-2867

## 1. Skill re-derivation
- [x] 1. `skills/engines/tensorfold/SKILL.md`: `ref`/`version` → `v1.2.9`, `pinned` →
  `539dc9d6044cad545cae3abeb019bb8fe202d35a`, `verified` → 2026-11-17; recipe-carry note records
  the `.zig-version` / `release_sms` / artifact-name review.

## 2. Companions
- [x] 2. `make generate-engine-params ENGINE=tensorfold` regenerates
  `containers/engines/dockerfiles/tensorfold/*`, `containers/engines/params/tensorfold.json`,
  `containers/engines/binaries.json`; no other engine's generated file moves.
- [x] 3. Real-tree asserts in `tests/test_engine_skills.py` (and any other real-tree file naming
  the tensorfold pin) follow the new version.

## 3. Gates
- [x] 4. `make check-engine-params`, `make check-engine-source`, `make check-engine-capabilities`,
  `make skills-validate` all rc=0; `pytest tests/test_engine_skills.py` rc=0.
- [x] 5. Docs pair: `agent-wiki/2026-11-17-engine-skill-tensorfold-2867.md` +
  `docs/changes.d/2026-11-17-engine-skill-tensorfold-2867.md`; `make changes-index` +
  `make check-docs` rc=0.
- [x] 6. `make openspec-validate NAME=engine-skill-tensorfold-2867` rc=0.

## 4. Ship verification
- [x] 7. The branch carries the full companion set proven end-to-end on the committed tree:
  `make test-unit` rc=0 (3963 passed, 13478 deselected, 1009.47s). Push/PR and the PR's green
  `engine-build-tensorfold-cuda` run id (issue AC 1) are recorded on the PR/issue, not a task here.
