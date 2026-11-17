# engine-base-cache-keyed-by-content

## Why

Every rebuild of an engine base image (cpu/cuda/rocm/vulkan, `render_base_dockerfile` outputs) is
effectively a cold toolchain build: `build_base` in `scripts/engine_image.py` passes a **fixed**
`{registry}llgenie/base-<backend>:buildcache` ref to the buildx registry layer cache, so a base
dockerfile change reuses the OLD content's cache namespace instead of getting a fresh one, and the
cache cannot be trusted to match the base that a cell resolves. Measured 2026-11-17 (run
44143247189): a cold ROCm base build sat 45-90+ minutes, exhausting the `engine-build-pr-trigger`
per-producer budget and re-shipping near-identical ROCm layers 28 times across four engine PRs (15
distinct cells).

The engine cells themselves already key their cache by variant (`buildcache-<variant>` in
`scripts/engine_image.py::build`); the shared bases are the one seam that does not. A base bump
(the #2840 class) made every dependent ROCm cell cold at once.

## What changes

`scripts/engine_skills.py::base_cache_ref(backend)` derives the buildx layer-cache ref from the
**same content hash** `base_tag` already carries — `llgenie/base-<backend>:buildcache-<sha256 of
the rendered Dockerfile>[:10]` — and `build_base` passes that ref to `_buildx` instead of the fixed
`:buildcache`. Because the ref is shared by the cache READ and WRITE, a base dockerfile change
starts a new cache namespace automatically (fresh key → buildx seeds it), while an unchanged base
keeps its warm namespace for the next replay. A hermetic check (`make check-engine-base-cache`,
run by `make test-unit`) proves each of the four base cache refs tracks the base content hash and
that a content perturbation re-keys the ref — no container or registry needed.

The export seam itself (`--cache-to type=registry` on the push build, and on the owner-guarded
`LLGENIE_CACHE_WRITE=1` verification build) already exists in `_buildx`; this change routes the base
through it with a correct, content-keyed ref so the export the acceptance criterion calls for becomes
warm-useful instead of stale-polluting.

## Out of scope

- The trigger's per-producer wait budget, published-skip probing and replacement-dispatch caps —
  its own issue (#2892).
- The `engine-build-push` FIFO concurrency-group design (the #178 discipline).
- The engine-cell cache refs (`buildcache-<variant>`) — already keyed; untouched here.
