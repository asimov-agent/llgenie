# Tasks — vllm-cuda-wheel

- [x] 1. `skills/engines/vllm/SKILL.md`: rewrite `install.cuda` to the wheel flow (curl + `sha256sum
      -c` hash-check + cu130 torch family then the wheel); record the wheel sha and drop the
      clone/`-r …/build/cuda.txt`/`build_rust.sh`/`-e .` steps for **cuda only**. `install.rocm` /
      `install.cpu` unchanged.
- [x] 2. `make generate-engine-params ENGINE=vllm`; commit the regenerated
      `containers/engines/params/vllm.json` and `containers/engines/dockerfiles/vllm/Dockerfile.cuda`.
- [x] 3. `scripts/engine_source_guard.py`: add `("vllm", "cuda")` to `KNOWN_NOT_SOURCE` so
      `make check-engine-source` stays green (the wheel install is a pull, not a source build).
- [x] 4. `tests/test_engine_skills.py`: hermetic test that the cuda install has no source step and
      DOES curl + hash-check the wheel; a regression back to `-e .`/`build_rust.sh` reds.
- [x] 5. `make check-engine-params`, `make check-engine-source` green (125 engine tests passed in
      the `llgenie/test` container); `make lane-preflight` green apart from the pending tasks 6-7.
- [ ] 6. Open PR (`fix(engines)` on the canonical asimov-agent/llgenie, body ends `closes #2386`);
      CI engine-image cuda cell green.
- [ ] 7. `agent-wiki/2026-11-09-vllm-cuda-wheel.md` + `docs/changes.d/` row + regenerated
      `CHANGES.md`; `make openspec-validate NAME=vllm-cuda-wheel` exits 0.
