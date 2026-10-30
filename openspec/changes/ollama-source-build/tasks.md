# Tasks — ollama-source-build

- [x] 1. `skills/engines/ollama/SKILL.md`: `install` clones `ollama/ollama` at `pinned:` and runs upstream's own Go build (`CGO_ENABLED=1 go build -trimpath -buildmode=pie -ldflags …`), plus the CPU runner from `llama/server --preset cpu`; `install.cuda` adds the `llama_cuda_v13_linux` runner, `install.rocm` the `GGML_HIP` runner with `AMDGPU_TARGETS` from the shared fat list, `install.vulkan` the `vulkan` runner.
- [x] 2. `container.<backend>` for cpu/cuda/rocm/vulkan: `prebuilt: true` and the `ollama/ollama` base dropped, `runtime: true` + `runtime_copy` of `{prefix}/{version}/bin` and `{prefix}/{version}/lib`, `apt: [golang-go]`.
- [x] 3. `make generate-engine-params ENGINE=ollama`; the regenerated `containers/engines/params/ollama.json` and the four `containers/engines/dockerfiles/ollama/Dockerfile.<arch>` are committed.
- [x] 4. `tests/test_engine_source_guard.py`: the census moves to 30 source / 1 prebuilt; `tests/test_engine_skills.py`: the tarball test becomes a source-build test and the official-image test drops its ollama rows.
- [x] 5. `make check-engine-source`, `make check-engine-params`, `make check-engine-coverage` are green (30 source / 1 prebuilt, only `litert/cpu` tracked; 0 stale; OK), and the affected test files pass (107 passed).
- [x] 6. Per-cell `make build-engine ENGINE=ollama ARCH=<arch>` + `make test-engine-stage ENGINE=ollama ARCH=<arch> TEST=detect` exercised for all four cells (cpu/cuda/rocm/vulkan built; each detect reports `installed client version is 0.40.12`), and the cpu image served a model and answered on `/v1/chat/completions` (`make test-engine ENGINE=ollama ARCH=cpu`). Results are recorded per cell in the PR body.
- [x] 7. `make test-unit` green (full hermetic suite: 15034 passed, 13 deselected; its one red — `tests/test_engine_bump.py::test_changed_engines_scopes_matrix` — was the uncommitted-tree artifact and is green on the commit).
- [x] 8. `README.md` + `docs/ENGINES.md` "prebuilt cells" passages updated (ollama ×4 now source builds).
- [x] 9. `agent-wiki/2026-10-30-ollama-source-build.md` + the `docs/changes.d` fragment (+ rendered `CHANGES.md` row) written in the same commit.
- [x] 10. `make openspec-validate NAME=ollama-source-build` exits 0 and `make check-docs` is green.
