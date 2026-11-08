# engine-build-local-build-driver — a local build pays the container driver's export only when it exports a cache

## Why

`engine-build` run `42326740375` (`workflow_dispatch`, head `05a4f2fd`, job
`engine-build-freetoken-rocm`, job id `128263747521`) failed `make build-engine ENGINE=freetoken
ARCH=rocm` with

```
#12 ERROR: write /opt/venv/lib/python3.12/site-packages/torch/lib/hipblaslt/library/TensileLibrary_...gfx1201.co: no space left on device
ERROR: failed to build: failed to solve: rpc error: code = Unknown desc = write ...: no space left on device
make: *** [Makefile:1324: build-engine] Error 1
```

on a 145 GiB runner with **107 GiB free** (the `Disk headroom` step printed `free_gb=106`, floor 30).
The same cell, same image, same runner size had gone **green** 2 hours earlier (run `41957934540`,
job `127017336229`, 104 GiB free) and its image is published at the current tag
(`ba31db2e-a724f1d8-rocm`, 16.10 GiB compressed).

The difference is the builder driver, not the image:

- green run `41957934540`:
  `docker buildx build --progress=plain --builder default --no-cache -t ... --load`
- red run `42326740375`:
  `docker buildx build --progress=plain --no-cache -t ... --load` (the docker-container builder)

`98c76aae` (issue #1747) made the local path stay on the active docker-container builder whenever
`LLGENIE_CACHE_WRITE=1`, because only that driver can export `--cache-to type=registry`. But the
gate read `not CACHE_WRITE` alone: a **forced** build passes neither `--cache-from` nor `--cache-to`
(it consults neither cache side), so it has nothing to export, yet it still paid the container
driver's local path — which writes the whole image as a tar and then unpacks it into dockerd on top
of the builder's own content store, about **3x the unpacked image**. For freetoken/rocm
(~35 GiB unpacked) that is ~105 GiB of the 107 GiB free: ENOSPC mid-load. The same commit's
consequence is visible on 2026-11-05: run `41957934540` (02:51Z) green, run `41971301136` (05:00Z,
same cell, `--load` on the container builder) red with `no space left on device` writing
`torch/lib/aotriton.images/...aks2`.

## What changes

Two things, both in `scripts/engine_image.py`:

1. **The driver gate asks whether THIS build exports a cache**, not whether the flag is set:
   `cache_export = CACHE_WRITE and REGISTRY and not push and not force and not no_cache_export`.
   A forced local build (or a push, which streams to the registry) exports nothing, so it runs on
   the `default` docker driver and never pays the tar + unpack.
2. **`NO_CACHE_EXPORT`** — a committed per-cell map, keyed `(engine id, variant)` exactly like
   `DISABLED`, naming cells whose image cannot afford the container driver's export+load even on an
   unforced run. `freetoken/rocm` is its first entry, with its measured footprint. Those cells'
   *local* builds run on the docker driver and skip the cache read/write (a printed note, never a
   silent skip). Their **publish** builds are untouched: `--push` streams to the registry with no
   local export, so the cache is still warmed there.

- `scripts/engine_image.py`: `NO_CACHE_EXPORT`, `_buildx(..., no_cache_export=...)`, `build()`
  passes it for a non-pushing build.
- `tests/test_engine_force_rebuild.py`: four tests (forced build -> docker driver; a listed cell ->
  docker driver, no cache flags; an unlisted cell -> container builder + both cache sides; the map
  names a committed cell).

## Out of scope

- The engine pin, its Dockerfile and its params (`freetoken` stays at `ba31db2e`, rocm install
  unchanged) — nothing about the image itself changes.
- Shrinking the image (a leaner ROCm base, pruning the torch wheel's unused gfx trees): a real
  follow-up that would also help users, filed separately rather than folded in here.
- The other cells in that run (`tensorrt-llm-cuda`, `mlx-cpu`, `tensorfold-cuda`) — separate
  failures, tracked in their own issues.
- Any gate weakening: no test is loosened, and the disk-floor policy from the closed #1933 stays
  out of this change.

## Who

llgenie-engine-improver (this lane owns the engine build/serve loop; #1915 is its reactor-report).

## Measured verification (this lane, at the fix head)

- `tests/test_engine_force_rebuild.py` + `tests/test_engine_image_matrix.py` +
  `tests/test_engine_build_workflow.py` = **69 passed**, including the four new tests (30 passed in
  `test_engine_force_rebuild.py` alone).
- The A/B evidence above is from the real failing/passing runs, not a local build (this lane never
  builds an engine image on the host).
- A single-cell re-dispatch of `engine-build` with `engine=freetoken arch=rocm force=true` at the
  fix head is the cell-level proof; its run id is reported on the PR and the issue.
