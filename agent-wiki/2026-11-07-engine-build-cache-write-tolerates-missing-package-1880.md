# engine-build: cache write tolerates an engine not yet on GHCR (#1880)

The default `make engine-build` sweep red on `engine-build-tensorfold-cuda` because its
`--cache-to type=registry,ref=ghcr.io/asimov-agent/llgenie/tensorfold:buildcache-cuda` failed
with `not found`: the tensorfold package does not exist on GHCR yet, so buildx cannot create a
cache ref under a namespace that is not there. The read side already built COLD when a cache
ref is absent (issue #1842); the write side did not.

Fix: `scripts/engine_image.py` gains `_cache_write_args()`, mirroring `_cache_read_args()`. It
probes the cache ref with `docker buildx imagetools inspect` and, when the image is absent,
skips the `--cache-to` write (a printed `cold build (cache write skipped; #1880)` note, never a
silent skip, #1796) so the build proceeds COLD instead of red. When the engine's package IS on
the registry the privileged `CACHE_WRITE=1` owner-guarded build still seeds the cache for the
next run. The cache is seeded as soon as the engine's package exists (a later publish), so the
write is only ever skipped for an engine that has never been published at all. Tests:
`test_a_missing_cache_image_builds_cold_not_red` now asserts no `--cache-to` on a missing ref,
and `test_a_present_cache_image_still_writes_when_privileged` asserts the write survives when
the ref exists.
