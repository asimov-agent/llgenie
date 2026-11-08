# 2026-11-08 — engine-build: a local build pays the container driver's export only when it exports a cache (issue #1915)

Issue: [#1915](https://github.com/asimov-agent/llgenie/issues/1915)
OpenSpec: `openspec/changes/engine-build-local-build-driver`
PR: *(this change — ready-for-review at the fix head; the earlier vehicle #1933 was closed unmerged and is not reopened)*

## The measurement (why PR #1933's diagnosis is not the fix)

The failing cell is `make build-engine ENGINE=freetoken ARCH=rocm`, run `42326740375`
(`workflow_dispatch`, head `05a4f2fd`, job `engine-build-freetoken-rocm`, job id `128263747521`,
step 6). The failing step's own log, at 2026-11-07T02:22:02Z:

```
#12 ERROR: write /opt/venv/lib/python3.12/site-packages/torch/lib/hipblaslt/library/TensileLibrary_F8F8_..._gfx1201.co: no space left on device
ERROR: failed to build: failed to solve: rpc error: code = Unknown desc = write ...: no space left on device
make: *** [Makefile:1324: build-engine] Error 1
[engine-image] FAIL build llgenie/<engine id>:ba31db2e-a724f1d8-rocm (exit 1)
```

The `Disk headroom` step in the same job printed `free_gb=106` and `/dev/root 145G 38G 107G 26%` —
so the flat 30 GiB floor of #1893 passed and the build died 22 minutes later. PR #1933 (closed
unmerged) proposed a *per-cell floor*, i.e. fail fast instead of a slow ENOSPC. That is a good
diagnostic but it never makes the cell green, and it explicitly listed `freetoken-rocm` as out of
scope — so it could not satisfy #1915's acceptance criteria. The per-cell floor is not this change.

## The actual cause: the builder DRIVER, proven A/B on the same cell and runner size

| run | when | buildx command | free disk | result |
|---|---|---|---|---|
| `41957934540` (job `127017336229`) | 2026-11-05 02:53Z | `--builder default --no-cache ... --load` | 104 GiB | **green**, image published at `ba31db2e-a724f1d8-rocm` |
| `41971301136` (job `127060077709`) | 2026-11-05 05:04Z | `--no-cache ... --load` (container builder) | ~107 GiB | red `no space left on device` (`torch/lib/aotriton.images/...aks2`) |
| `42326740375` (job `128263747521`) | 2026-11-07 02:00Z | `--no-cache ... --load` (container builder) | 107 GiB | red `no space left on device` (`hipblaslt/library/...gfx1201.co`) |

Both red runs had `LLGENIE_CACHE_WRITE=1` and `force=true`. `98c76aae` (issue #1747) moved the local
path onto the active docker-container builder whenever `LLGENIE_CACHE_WRITE` is set, because only
that driver can EXPORT `--cache-to type=registry`. But the gate read the flag alone: a forced build
passes neither `--cache-from` nor `--cache-to` — there is nothing to export — and yet paid the
container driver's local path, which writes the whole image as a tar and then unpacks it into
dockerd on top of the builder's own content store: about **3x the unpacked image**. The published
image is 16.10 GiB compressed (~35 GiB unpacked), so ~105 GiB of the 107 GiB free: ENOSPC mid-load.

## The fix (scripts/engine_image.py)

1. The driver gate asks whether **this build exports a cache**:
   `cache_export = CACHE_WRITE and REGISTRY and not push and not force and not no_cache_export`.
   Forced local builds and push builds (which stream to the registry) export nothing and run on the
   cheap `default` docker driver.
2. `NO_CACHE_EXPORT` — a committed per-cell map, keyed `(engine id, variant)` exactly like
   `DISABLED`, for cells whose image cannot afford the container driver's export+load even unforced.
   First entry `("freetoken", "rocm")` with its measured footprint. Those cells' local builds run on
   the docker driver and skip the cache read/write with a printed note; their publish builds are
   untouched and still warm the registry cache.

## Verified

- `tests/test_engine_force_rebuild.py` — **30 passed**, including four new tests
  (`test_a_forced_local_build_never_needs_the_container_driver`,
  `test_a_cell_that_cannot_afford_the_export_builds_on_the_docker_driver`,
  `test_a_cell_not_in_the_map_still_exports_its_cache`,
  `test_the_no_cache_export_map_names_a_real_committed_cell`). The existing
  `test_a_cache_write_build_stays_on_the_container_builder` (#1747) still passes, so the cache
  export for ordinary cells is preserved.
- `test_engine_force_rebuild.py` + `test_engine_image_matrix.py` + `test_engine_build_workflow.py`
  = **69 passed**.
- The cell-level proof is a single-cell dispatch at the fix head
  (`gh workflow run 395994204 --ref <branch> --field engine=freetoken --field arch=rocm --field force=true`);
  its run id is reported on the PR. No engine image was built on this host — this lane pulls and
  runs, CI builds.

## Left open

Shrinking the image itself (a leaner ROCm base or pruning the torch wheel's unused gfx trees) is a
separate, user-visible improvement: it would remove the cell from `NO_CACHE_EXPORT` entirely.
