# Change: hf-cli-pin

## Why

Issue #2380: the engine-build `hf CLI (tiny test model)` step ran an inline
`uv tool install "huggingface_hub[cli]>=0.30"`, bypassing the repository's lock
(`tools/requirements.in` pins `huggingface_hub[cli]==1.30.0`). In run 42558839616 the
resolver picked 2.4.0, whose `cli` extra was removed — every cell logged
`The package huggingface-hub==2.4.0 does not have an extra named cli`. The floating
install also violates the rule that every CI command is a make target.

## What Changes

- The engine-build step routes through a new `make hf-cli-install` target that
  resolves the exact `huggingface_hub==<pin>` spec from `tools/requirements.in`.
- The stale `[cli]` extra is dropped from the compile input (current
  `huggingface_hub` ships `hf` in the base package; the extra only warns), and
  `tools/requirements.txt` is recompiled via `make generate-requirements`.
- A lock test ties the step, the target and the compile input together; stale
  `[cli]` mentions in `scripts/ci_health.py` / `scripts/llgenie_serve.py` text are corrected.

## Impact

- Affected specs: `engine-build-pins` (new capability)
- Affected code: `.github/workflows/engine-build.yml`, `Makefile`,
  `tools/requirements.in`, `tools/requirements.txt`, `tests/test_requirements_pins.py`,
  `scripts/ci_health.py`, `scripts/llgenie_serve.py`, `docs/ENGINES.md`
