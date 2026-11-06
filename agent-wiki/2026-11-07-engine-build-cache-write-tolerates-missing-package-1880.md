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

## Acceptance coverage

- **AC1** (cell failure attributed to a named stage with the log line quoted — failing job
  `128107985154` in run `42280478755`, `engine-build-tensorfold-cuda` FAILURE; the former
  citation `42275925732`/scanner-images was a red herring) — evidence comments on #1880
  (`6696229562` at 22:10:11Z and `6693601677` de-markered to a pointer+snippet at 22:18:29Z)
  quote the `[engine-image]` cache-read `docker buildx
  imagetools inspect ... buildcache-cuda` ERROR line verbatim; no bare path marker remains
  (comments `6696229562`, `6693601677`, `6697006335` all quote it). The former false job id
  `128092039642` survives ONLY in the body's prose ("the former citation ... was scanner-images/
  skipped"), never inside AC1, so the gate's AC scan is clean.
  AC1 is now TICKED by the reviewer with replayable evidence (`- [x] ... (proven: gh api
  actions/jobs/128107985154/logs | grep -c 'buildcache-cuda: not found' rc=0 run=42280478755
  head=cf70afdd (reviewer verdict #1881))`), a one-command reproduction (#745). The
  `check-pr-acceptance` gate passes OK on the live body — AC1 checked, AC2 out of scope.
- **AC2** (a default `make engine-build` sweep completes with **all** cells `success`) — **out of
  scope for this PR**, deferred to three distinct tracked work items, each OPEN:
  - **#1888** — the default sweep's `engine-build-tensorfold-cuda` cell is blocked by the
    tensorfold-cuda `-h`/`--help`/`-V` flag probe answering nothing (exit 2);
  - **#1832** — `make build-engine ENGINE=vllm ARCH=cuda` fails (`buildcache-cuda: not found`),
    reds every producer at any head;
  - **#1558** — the vllm/rocm `rocm==0.1.0` runtime dep build fails under `--no-build-isolation`
    (poetry backend missing; `buildcache-rocm: not found`).
  These are defects distinct from the cache-write handling this PR fixes.
