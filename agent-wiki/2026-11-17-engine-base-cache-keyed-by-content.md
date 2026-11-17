# Engine base buildx cache keyed by content (2026-11-17)

Implements issue #2891. Every rebuild of an engine base image (cpu/cuda/rocm/vulkan,
`render_base_dockerfile` outputs) paid a cold toolchain build: `build_base` in
`scripts/engine_image.py` passed a **fixed** `llgenie/base-<backend>:buildcache` ref to the buildx
registry layer cache, so a base dockerfile change reused the OLD content's cache namespace and an
unchanged base could not trust its cache. Measured 2026-11-17 (run 44143247189): a cold ROCm base
build sat 45-90+ minutes and the four engine PRs re-shipped near-identical ROCm layers 28 times
(15 distinct cells). The engine cells already key their cache by variant (`buildcache-<variant>`);
the shared bases were the one seam that did not.

## Decision

- New `scripts/engine_skills.py::base_cache_ref(backend)` derives the buildx layer-cache ref from
  the **same content hash** `base_tag` already carries —
  `llgenie/base-<backend>:buildcache-<sha256(rendered base Dockerfile)[:10]>` — and `build_base`
  passes that ref to `_buildx` instead of the fixed `:buildcache`.
- Because the read and write share one ref, a base Dockerfile change starts a fresh cache namespace
  automatically (fresh key → buildx seeds it); an unchanged base keeps it warm for the next replay.
  The export seam (`--cache-to type=registry` on push, and on the owner-guarded
  `LLGENIE_CACHE_WRITE=1` verification build) already existed in `_buildx`; this change routes the
  base through it with a correct, content-keyed ref.
- Hermetic proof, no container/registry: `tests/test_engine_skills.py::test_build_base_uses_a_content_keyed_cache_ref`
  asserts (a) all four base cache refs track their base content hash, (b) a perturbed Dockerfile
  re-keys the ref, (c) the seam passes the content-keyed ref to `_buildx`. Wired as the documented
  `make check-engine-base-cache` target and covered by `make test-unit` in CI.
- Openspec change `engine-base-cache-keyed-by-content` accompanies the code; spec scenarios carry
  `- **Test:**` lines.

## Out of scope

- The trigger's per-producer wait budget, published-skip probing and replacement caps — its own
  issue #2892.
- The `engine-build-push` FIFO concurrency-group design (the #178 discipline).
- The engine-cell cache refs (`buildcache-<variant>`) — already content-keyed; untouched.

## PR

Completes openspec change engine-base-cache-keyed-by-content. Closes #2891. Loop gate green,
openspec validate passes, all tasks ticked.
