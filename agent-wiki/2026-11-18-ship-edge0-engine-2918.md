# 2026-11-18 — ship the edge0 engine as a pack-format model (issue #2918, PR #<TBD>)

Shipping `edge0` (the registry engine behind `edge0-145b`, registered 2026-11-17) as llgenie's
first pack-format engine: a `skills/engines/edge0/SKILL.md` declaring `model_contract: "pack"`
with the upstream EDGE0.md v5 part wiring, the generated CUDA-13 Dockerfile lane, and the deferred
decision in `data/unsupported-engines.json` closed on the shipped skill.

## What was verified

- **Skill** (`skills/engines/edge0/SKILL.md`): `servable: true`, `backends: [cuda]`,
  `formats: [pack]`, `model_contract: "pack"` + `pack.parts`/`pack.config_env` matching the v5
  server-config template read from upstream (`Edge0-AI/Edge0` `edge0-strata/edge0/
  models/edge0-145b.json`, fetched 2026-11-18): parts `model-skeleton.gguf`, `ple-fp8.gguf`,
  `profile.bin`, `experts.bin`, `labels.bin`, `dense.bin`, `mtp`, `tokenizer`; `config_env`
  `STRATA_LATENT_A→experts.bin`, `STRATA_LATENT_LABELS→labels.bin`, `STRATA_LATENT_DENSE→dense.bin`.
  The Linux CUDA build follows EDGE0.md v5 "Build (Linux, NVIDIA)" (CMake+Ninja,
  `CMAKE_CUDA_COMPILER=$(command -v nvcc)`, `CMAKE_CUDA_ARCHITECTURES=${cuda_arch}`,
  `STRATA_ENABLE_CUDA=ON`, `STRATA_GGML_DIR` = llama.cpp snapshot `3cf03257f…` in
  `third_party/llama.cpp`, `cmake --build build --target strata`).
- **Lane** (`make generate-engine-params ENGINE=edge0`): wrote
  `containers/engines/params/edge0.json` (cuda variant, `nvidia/cuda:13.0.2-devel-ubuntu24.04`,
  arch `75;80;86;89;90;120`), `containers/engines/dockerfiles/edge0/Dockerfile.cuda`, and the
  `containers/engines/binaries.json` entry. `make check-engine-params` → 0 stale. The CI matrix
  resolves exactly one `edge0`/`cuda` cell (`smoke: false`, `test: detect`).
- **Gap closure**: `data/unsupported-engines.json` no longer defers `edge0`; `make
  render-engine-skill-gap` re-derived `data/engine-skill-gap.json` (edge0 `shipped`, image true,
  variants `[cuda]`, top engine for `edge0-145b` on cuda) and `make check-engine-skill-gap` exits 0
  (50 engines, 18 skills, unresolved 0).
- **Tests**: `tests/test_engine_edge0.py` (5 hermetic cases) green via
  `python3 -m pytest`.

## Not covered (human gate)

- The live host serve proof (`make test-engine-host ENGINE=edge0` on a real `edge0-145b` pack)
  needs explicit human permission to start inference engines (repo rule); it is its own linked
  issue **#2922**.

## Sweep rebase (onto main `18d33358c3`, 2026-11-18)

The lane opened at main `0a2a7f326`, before PR #2919 (pack contract) merged. Rebasing and
re-running the gates surfaced what the original container-less run left undone, all fixed here:

- `make generate-engine-params ENGINE=edge0` now emits the pack keys into `params/edge0.json`
  (the #2909 pass-through is on main; the earlier "cannot carry" note is obsolete).
- `data/engine-capabilities.json` gains the `edge0` row (`archs: [cuda]`, `formats: [pack]`) —
  `check-engine-capabilities` E5 + `can_serve("edge0","cuda")` red until it exists.
- The skill's ggml fetch moved from a `curl … archive.tar.gz` download (source-guard violation:
  `prebuilt=false` cell downloading a built artefact) to a guarded pinned `git clone` +
  `git checkout 3cf03257…` — idempotent and artefact-free.
- `make render-trend-list-matrix` re-recorded `trend-list-matrix.json` (81 cases) and
  `hub-snapshot.json` (103 Hub answers) for the new `Edge0/Edge0-145B-q3k` fixture routes; the
  hub-snapshot/trend-matrix tests reproduce with no unrecorded route.
