## Why

The 2026-11-16 ollama bump (PR #2855) moved the generated Dockerfiles to ollama `v0.40.16`
without carrying its companions: `containers/engines/binaries.json` still expected
`/opt/llgenie/engines/ollama/0.40.15/bin/ollama`, so both build cells failed their binary stage —
`engine-build-ollama-cuda` "missing binary file: …/0.40.15/bin/ollama" and `engine-build-ollama-cpu`
"…0.40.15/bin/ollama probed non-zero (1)" (runs 43911760642 / 43908916000). The bump PR was closed
superseded, so main still builds ollama at `v0.40.15` while upstream moved. This change re-derives
the ollama engine skill at `v0.40.16` and lands the complete companion set.

## What Changes

- `skills/engines/ollama/SKILL.md`: `ref`/`version` → `v0.40.16` (upstream tag object
  `d63b702609c4300a2ca07be2bdb0adb9834725e5`), `pinned` → that sha, `verified` → 2026-11-17. The
  recipe was re-checked at the new pin: the only `v0.40.15...v0.40.16` diff touching the build is
  `llama/server/CMakePresets.json` (arm64-windows `CMAKE_CUDA_ARCHITECTURES` widened to
  `103;121`) — no Linux cpu/cuda/rocm preset changes — so the install steps carry unchanged.
- `make generate-engine-params ENGINE=ollama` regenerates the companions: the four
  `containers/engines/dockerfiles/ollama/Dockerfile.<arch>` COPY paths and
  `containers/engines/binaries.json` binary paths to `…/ollama/0.40.16/…`.
- `tests/test_engine_skills.py`: the ollama real-tree assertions (`git clone -b v0.40.15`,
  `-X=github.com/ollama/ollama/version.Version=0.40.15`) follow the new pin.

## Impact

- Affected specs: `ollama-engine-build` (new capability: the shipped ollama cells pin one version
  across skill, generated params/dockerfiles, and binaries manifest)
- Affected code: `skills/engines/ollama/SKILL.md`, `containers/engines/dockerfiles/ollama/*`,
  `containers/engines/binaries.json`, `containers/engines/params/ollama.json`,
  `tests/test_engine_skills.py`
- The PR's `engine-build-ollama-cpu` and `engine-build-ollama-cuda` jobs are the live proof
  (issue #2866 AC 1); no engine image is built on the host.
