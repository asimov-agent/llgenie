# engine-selection-canonical — Tasks

Issue: [#2516](https://github.com/asimov-agent/llgenie/issues/2516)

- [x] 1. `scripts/check_engine_pins_published.py::_probe` prints `[select] <engine-id> <variant> <tag>` per unpublished cell on the `--all` sweep, with the committed id (dots intact).
- [x] 2. `registry-liveness.yml` dispatch step builds its `gh workflow run` inputs only from `[select]` lines; no engine id is parsed from a package URL.
- [x] 3. `scripts/engine_image.py matrix()` exits non-zero naming the selection when an explicit engine/arch resolves to zero committed cells; the placeholder remains only for unscoped/`--changed` sweeps.
- [x] 4. `make engine-build-matrix ENGINE=<typo>` and `make build-engines ENGINE=<typo>` fail loudly instead of silent no-ops (verified via the matrix CLI).
- [x] 5. Tests pin the three behaviours: `tests/test_check_engine_pins_published.py` (dotted `[select]` ids, `[select]`-only dispatch) and `tests/test_engine_image_matrix.py` (unknown-selection hard-fail incl. the `llama-cpp` replay and the unscoped placeholder) — all green in `make test-unit`.
- [x] 6. `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs` pass; `make openspec-validate NAME=engine-selection-canonical` exits 0.
