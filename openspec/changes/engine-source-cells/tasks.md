# Tasks — engine-source-cells

- [x] 1. `skills/engines/mlx/SKILL.md`: `install.cpu`/`install.cuda` build mlx's core from `ml-explore/mlx` @ `1f8e74e3` and `mlx-lm` from its pinned tree; `container.{cpu,cuda}.apt` carries the BLAS/LAPACK/python headers, `container.cuda` adds cuDNN's dev headers, and `-DMLX_CUDA_ARCHITECTURES` comes from the shared fat list.
- [x] 2. `skills/engines/freetoken/SKILL.md`: `install.cuda` clones at `ba31db2e` and runs upstream's `setup.py` (own CUDA fat arch list); `container.cuda.apt` carries `python3-dev`.
- [x] 3. `skills/engines/tensorfold/SKILL.md`: `install.cuda` builds the Zig server at `c425f4cc` with `zig build -Dnvcc=… -Dsm=80,86,120,121` (upstream's `release_sms`), the compiler coming from PyPI `ziglang`; the release archive is gone.
- [x] 4. `skills/engines/litert/SKILL.md`: dated decision with the measured attempt (Bazel repository-mapping failure in 92 s, 4.5 GB cache, Git-LFS `libLiteRt.so`); the cell keeps its wheel install and its `KNOWN_NOT_SOURCE` entry, because `prebuilt: true` in this generator means "FROM the engine's upstream image" and litert has none.
- [x] 5. `make generate-engine-params ENGINE=<id>` for each converted engine; the regenerated `containers/engines/params/*.json` + `containers/engines/dockerfiles/**` are committed.
- [x] 6. `scripts/engine_source_guard.py`: `KNOWN_NOT_SOURCE` is down to `litert/cpu`, and `zig build` is a recognised build signal.
- [x] 7. `tests/test_engine_source_guard.py`: the census, the converted cells' committed params, the Zig signal and the tracked-exception case are asserted.
- [x] 8. Verify each converted cell on this host: `make build-engine ENGINE=<id> ARCH=<arch>` then `make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect`.
- [x] 9. `make check-engine-source`, `make check-engine-params`, `make check-engine-coverage`, `make test-unit` green.
- [x] 10. `README.md` engine-image rule + recorded exception, `agent-wiki/2026-10-29-engine-source-cells.md`, `CHANGES.md` row.
- [x] 11. The nine honestly-labelled `prebuilt: true` cells are filed as linked issues (#936 ollama, #937 vllm, #938 sglang/cuda, #939 tensorrt-llm) and named in the PR's `Not covered`.
- [x] 12. `make openspec-validate NAME=engine-source-cells` exits 0 and every task above is ticked.
