# 2026-11-17 — engine-skill-ollama-2866 (ollama re-derived at v0.40.16, companions complete)

Issue: #2866 (PR closes it). OpenSpec change: `engine-skill-ollama-2866`.

## What was verified against the spec

- Root cause measured from the closed bump PR #2855's CI logs: the bump moved the generated
  Dockerfiles to `v0.40.16` but `containers/engines/binaries.json` still probed
  `…/ollama/0.40.15/bin/ollama` — `engine-build-ollama-cuda` "missing binary file"
  (run 43911760642) and `engine-build-ollama-cpu` "probed non-zero (1)" (run 43908916000).
  A companion gap, exactly the #2865 defect family.
- Recipe re-derivation: upstream `v0.40.15...v0.40.16` (tag object
  `d63b702609c4300a2ca07be2bdb0adb9834725e5`, verified via `gh api
  repos/ollama/ollama/git/refs/tags/v0.40.16`) touches the build only in
  `llama/server/CMakePresets.json` — `CMAKE_CUDA_ARCHITECTURES` widened to `103;121` on the
  windows-arm64 preset. Linux cpu/cuda/rocm install steps carry unchanged.
- `make generate-engine-params ENGINE=ollama` (rc=0) regenerated exactly the ollama companions:
  4 Dockerfiles, `params/ollama.json`, `binaries.json` — all binary paths now
  `/opt/llgenie/engines/ollama/0.40.16/bin/ollama`; no other engine's generated file moved
  (`git status` scoped to ollama paths).
- Gates run locally at this head: `make check-engine-params`, `check-engine-source`,
  `check-engine-capabilities`, `skills-validate` all rc=0; `pytest tests/test_engine_skills.py`
  103 passed. Full `make test-unit` recorded in `tasks.md`.
- AC1 ("cpu and cuda cells build green at v0.40.16") is proven by this PR's
  `engine-build-ollama-cpu` / `engine-build-ollama-cuda` run ids — recorded here once CI reports
  them (engine images build in CI only, per the standing directive).

## Key decisions

- No host-side engine image build: proof lives in the PR's engine-build jobs.
- The synthetic `v0.40.15` fixtures in `test_engine_bump.py` / the probe-policy fixtures in
  `test_engine_skills.py` stay — they are sample data, not real-tree assertions; only the two
  real-tree asserts (clone tag, `-X version.Version` ldflag) followed the pin.

## Current status

Branch `feat/engine-skill-ollama-2866` from main `92c44dc87`; skill + companions + tests + docs +
OpenSpec complete. #2867 (tensorfold) and #2868 (strata) keep the same repair shape for their own
PRs after this one lands.
