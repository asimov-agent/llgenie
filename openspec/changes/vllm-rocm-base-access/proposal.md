# Change: vllm/rocm base access for the non-root runtime user (#2553)

## Why

`make engine` CI run 43206254966 left the vllm/rocm cell unpublished, and the targeted
rebuild (dispatch run 43221661126, main `7701ee038`) reproduced a real image defect, not a
flake: as the mandatory runtime `USER 1000`, the vllm console script `/opt/python/bin/vllm`
exits 126 (Permission denied) and the detect probe fails `ModuleNotFoundError: No module
named 'vllm'`. Measured via the base image's Docker Hub config blob
(`sha256:2d41964e…`): `rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0`
hosts vllm in a root-built uv venv at `/opt/python` with restrictive modes, while the CUDA
cell works because its base ships vllm in the world-readable system python. The cell stays
unpublished, the fleet is stuck at 26/28, and every retry burns ~65 min of runner time.

## What Changes

- `scripts/engine_skills.py` gains one container-spec key, `base_access` (list of base
  install dirs), rendered into a single `RUN` immediately before the trailing
  `USER 1000:1000` of any variant that declares it. The `RUN` opens **directory metadata**
  for uid 1000 (`find <dir> -type d -exec chmod a+rx`) plus the small `<dir>/bin` entries —
  never a recursive chmod over regular files outside `bin`, which would copy the ~15 GB
  engine tree up into a new layer.
- `render_variant` attaches `base_access` ONLY to the variant dict that declared it. Each
  cell's image tag hashes its own variant params plus its committed Dockerfile
  (`engine_skills._image_inputs`), so only the declaring cell's digest moves: vllm cuda
  stays `4c1f3eee` (published tag stays reachable), cpu stays `524f7326`, and the broken
  rocm moves `db98981b` → `ba13b1d7` → `d04739cb` — moving that tag identity is the point, since the
  old rocm image is the broken one.
- `skills/engines/vllm/SKILL.md` `container.rocm` sets `base_access: ["/opt/python"]`;
  `make generate-engine-params` regenerates `containers/engines/dockerfiles/vllm/Dockerfile.rocm`
  (only that file changes; cuda/cpu variants stay byte-identical).
- After merge, one `workflow_dispatch` engine-build (`engine=vllm arch=rocm push=true`)
  publishes `vllm:3a4d82f5-db98981b-rocm` (issue #2553 / fleet AC in #2529).

## Impact

- Affected specs: `vllm-rocm-base-access` (new capability)
- Affected code: `scripts/engine_skills.py` (variant attach + renderer),
  `skills/engines/vllm/SKILL.md`, `containers/engines/dockerfiles/vllm/Dockerfile.rocm`
  (generated), `tests/test_engine_skills.py` (lock)
- NOT affected: every other engine's params variant, Dockerfile and binaries.json entry;
  the published vllm cuda/cpu cell tags (digests measured identical before/after).
