# Tasks — sglang-cuda-pip-bootstrap

- [x] 1. `skills/engines/sglang/SKILL.md`: the two `install.cuda` steps that call
  `python3 -m pip install` change to `uv pip install --system
  --break-system-packages` (dropping `--no-cache-dir`), matching the sibling
  cuda engines' recipe; the editable main-package spec is corrected from
  `-e 'python[all]'` to `-e '.[all]'` (the step `cd`s into `{src}/python`, so
  `python` was a non-existent relative path that fails the uv install).
- [x] 2. `make generate-engine-params ENGINE=sglang`: the regenerated
  `containers/engines/params/sglang.json` + `containers/engines/dockerfiles/sglang/Dockerfile.cuda`
  are committed.
- [x] 3. `make check-engine-params`, `make check-engine-source`,
  `make check-engine-coverage` green; affected engine-skills tests pass
  (`test_sglang_cuda_install_uses_uv_not_pip` added, 96/96 in `tests/test_engine_skills.py`).
- [ ] 4. The `engine-image-sglang-cuda` cell is proven on a CI run from this PR
  head (`make build-engine ENGINE=sglang ARCH=cuda` then
  `make test-engine-stage TEST=detect`) — no `No module named pip`.
- [x] 5. `make test-unit` green (full hermetic suite) — 2690 passed, RC=0.
- [x] 6. `agent-wiki/2026-10-31-sglang-cuda-pip-bootstrap.md` + `CHANGES.md` row
  (+ `docs/changes.d/`), OpenSpec `tasks.md` all ticked.
- [x] 7. `make openspec-validate NAME=sglang-cuda-pip-bootstrap` exits 0.
