# Proposal: ship-edge0-engine-2918

## Why

The registry's only `edge0` model, `edge0-145b`, advertises engine `edge0`, but no llgenie engine
ships for it: `containers/engines/params/edge0.json`, `containers/engines/dockerfiles/edge0/`, and a
`skills/engines/edge0/SKILL.md` are all absent, and `data/unsupported-engines.json`'s
`.engines["edge0"]` stays `decision: deferred` (issue #2903's dated decision). The pack model
contract (issue #2909, PR #2919) defined the seams this engine consumes — params
`model_contract: "pack"` with `pack.{parts, config_env}`, the launch binding every declared part at
`docker run` (`scripts/pack_contract.launch_env`) — but no shipped engine exercises them end to end.
Orphaned until it ships, the `edge0` row hides `edge0-145b` from the offer and the deferral cannot
close. Measured at main `0a2a7f326`: no `edge0` params/Dockerfile/skill, and the decision record
still defers.

## What Changes

1. **Ship the edge0 skill** (`skills/engines/edge0/SKILL.md`): `model_contract: "pack"` with the
   EDGE0.md v5 part wiring read from upstream (`Edge0-AI/Edge0` `edge0-strata/EDGE0.md` launch
   contract v5 + the `edge0/models/edge0-145b.json` server-config template): parts
   `model-skeleton.gguf`, `ple-fp8.gguf`, `profile.bin`, `experts.bin`, `labels.bin`, `dense.bin`,
   `mtp`, `tokenizer`, and `config_env` `STRATA_LATENT_A=experts.bin`,
   `STRATA_LATENT_LABELS=labels.bin`, `STRATA_LATENT_DENSE=dense.bin`. The Linux CUDA build follows
   EDGE0.md v5 exactly (CMake+Ninja against CUDA 13, `CMAKE_CUDA_COMPILER=$(command -v nvcc)`,
   `CMAKE_CUDA_ARCHITECTURES=${cuda_arch}`, `STRATA_ENABLE_CUDA=ON`, `STRATA_GGML_DIR` = the pinned
   llama.cpp snapshot `3cf03257f…` unpacked into `third_party/llama.cpp`, then `cmake --build build
   --target strata`; server venv `python3 -m venv` + `requirements.txt`, the EDGE0.md-sanctioned
   fallback for its `uv venv`).
2. **Dockerfile lane + build matrix:** `make generate-engine-params ENGINE=edge0` writes
   `containers/engines/params/edge0.json` (CUDA 13 devel base, fat arch list) and
   `containers/engines/dockerfiles/edge0/Dockerfile.cuda`; the engine enters the `engine-build`
   matrix via `scripts/engine_image.py matrix()` exactly like every engine (cuda, `test=detect` —
   a pack has no tiny smoke model, so the version test, not the CPU chat test).
3. **Close the deferral on a shipped skill:** `data/unsupported-engines.json` drops the `edge0`
   entry; `make render-engine-skill-gap` re-derives `data/engine-skill-gap.json` and
   `make check-engine-skill-gap` goes green on the SHIPPED skill instead of a re-recorded deferral.
4. **Test:** `tests/test_engine_edge0.py` locks the v5 part/config_env declaration, the CUDA-13
   base + matrix cell, the decision closure, and the v5 placeholder substitution that survives the
   repo's `_render` — hermetic, no network, auto-included by the aggregated unit suite.

## Impact

- Affected specs: `edge0-engine` (new capability)
- Affected code: `skills/engines/edge0/SKILL.md` (new), `containers/engines/params/edge0.json` +
  `containers/engines/dockerfiles/edge0/Dockerfile.cuda` + `containers/engines/binaries.json`
  (generated), `data/unsupported-engines.json` (edge0 decision removed),
  `data/engine-skill-gap.json` (re-rendered), `tests/test_engine_edge0.py` (new)
- Affected tests: new `tests/test_engine_edge0.py` (hermetic)

## Not covered

- **Host serve proof over a real pack** — `make test-engine-host` on `edge0-145b` as a pack
  directory: gated on explicit human permission to start inference engines on a host (repo rule),
  and on the pack launch binding arriving with #2909 (PR #2919, unmerged at main `0a2a7f326`).
- **Params carriage of `model_contract`/`pack`** — the generator pass-through that copies the pack
  keys from the skill into the params JSON (`scripts/engine_skills.py` `render_variant`/`image_spec`,
  part of #2909/PR #2919). Until #2919 merges, the edge0 params file carries the cuda variant
  without the pack keys (main's generator drops them); the skill is the source of truth and the
  merge of #2919 makes `make generate-engine-params` emit them. Both are the same #2909 dependency;
  neither is prose — #2909 names this issue's serve-proof and this issue names #2909 back.
