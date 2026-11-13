# Tasks: hf-cli-pin

- [x] Add `make hf-cli-install` resolving the exact pinned spec from `tools/requirements.in` (proved: disposable UV_TOOL_DIR run rc=0, `hf --version` -> 1.30.0)
- [x] Route the engine-build `hf CLI (tiny test model)` step through the target (no inline `uv tool install` remains in the workflow)
- [x] Drop the stale `[cli]` extra from `tools/requirements.in` and recompile `tools/requirements.txt` (`make generate-requirements` rc=0; compiled line is `huggingface-hub==1.30.0`)
- [x] Extend `tests/test_requirements_pins.py` with the step/target/compile-input lock test (23 passed rc=0)
- [x] Correct stale `[cli]` text in `scripts/ci_health.py` and `scripts/llgenie_serve.py`
- [x] Document the target in `docs/ENGINES.md`; agent-wiki note + changes.d fragment in the same commit
- [x] Gates green: `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make openspec-validate NAME=hf-cli-pin`
