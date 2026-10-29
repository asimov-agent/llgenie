# Tasks — engine-source-cells

- [ ] 1. `skills/engines/mlx/SKILL.md`: `install.cpu`/`install.cuda` build mlx's core from `ml-explore/mlx` @ `1f8e74e3` and `mlx-lm` from its pinned tree; `container.{cpu,cuda}.apt` carries the BLAS/LAPACK/python headers.
- [ ] 2. `skills/engines/freetoken/SKILL.md`: `install.cuda` clones at `ba31db2e` and runs upstream's `setup.py` (own CUDA fat arch list); `container.cuda.apt` carries `python3-dev`.
- [ ] 3. `skills/engines/tensorfold/SKILL.md`: `install.cuda` builds the Zig server at `c425f4cc` with its `nvcc` fatbin step, or carries the dated decision with the measured blocker.
- [ ] 4. `skills/engines/litert/SKILL.md`: dated decision with the measured attempt (Bazel/CMake, wall-clock, disk) and `prebuilt: true`.
- [ ] 5. `make generate-engine-params ENGINE=<id>` for each converted engine; commit `containers/engines/params/*.json` + `containers/engines/dockerfiles/**`.
- [ ] 6. `scripts/engine_source_guard.py`: delete the `KNOWN_NOT_SOURCE` entry of every converted cell.
- [ ] 7. `tests/test_engine_source_guard.py`: the converted cells' committed params are source builds after generation.
- [ ] 8. Verify each converted cell on this host: `make build-engine ENGINE=<id> ARCH=<arch>` then `make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect`.
- [ ] 9. `make check-engine-source`, `make check-engine-params`, `make check-engine-coverage`, `make test-unit` green.
- [ ] 10. `README.md` engine-image rule + recorded exception, `agent-wiki/2026-10-29-engine-source-cells.md`, `CHANGES.md` row.
- [ ] 11. The nine honestly-labelled `prebuilt: true` cells are filed as linked issues (ollama, vllm, sglang/cuda, tensorrt-llm) and named in `Not covered`.
- [ ] 12. `make openspec-validate NAME=engine-source-cells` exits 0 and every task above is ticked.
