# Tasks — engine-skill-ollama-2866

## 1. Skill re-derivation
- [x] 1. `skills/engines/ollama/SKILL.md`: `ref`/`version` → `v0.40.16`, `pinned` →
  `d63b702609c4300a2ca07be2bdb0adb9834725e5`, `verified` → 2026-11-17; recipe-carry note records
  the CMakePresets diff review.

## 2. Companions
- [x] 2. `make generate-engine-params ENGINE=ollama` regenerates
  `containers/engines/dockerfiles/ollama/*`, `containers/engines/params/ollama.json`,
  `containers/engines/binaries.json`; no other engine's generated file moves.
- [x] 3. `tests/test_engine_skills.py` ollama real-tree assertions follow the pin.

## 3. Gates
- [x] 4. `make check-engine-params`, `make check-engine-source`, `make check-engine-capabilities`,
  `make skills-validate` all rc=0; `pytest tests/test_engine_skills.py` rc=0.
- [x] 5. Docs pair: `agent-wiki/2026-11-17-engine-skill-ollama-2866.md` +
  `docs/changes.d/2026-11-17-engine-skill-ollama-2866.md`; `make check-docs` rc=0.
- [x] 6. `make openspec-validate NAME=engine-skill-ollama-2866` rc=0.

## 4. Ship verification
- [x] 7. The branch carries the full companion set proven end-to-end on the committed tree:
  `make test-unit` rc=0 (3963 passed, 13478 deselected, 1052.19s). Push/PR and the PR's green
  `engine-build-ollama-cpu` / `engine-build-ollama-cuda` run ids are recorded on the PR/issue,
  not a task here.
