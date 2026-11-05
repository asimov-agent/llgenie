# engine-build cache write stays on the docker-container builder

## Background (measured 2026-11-05)

`engine-build` workflow_dispatch run **41944882169** (head `689cc6c5`, PR #1696)
fails its GPU cells — `engine-build-vllm-rocm` (job 126975033244) and
`engine-build-vllm-cuda` (126975033081) — with:

```
ERROR: failed to build: Cache export is not supported for the docker driver.
make: *** [Makefile:1306: build-engine] Error 1
```

The job log shows the workflow creating the right builder — `docker buildx create
... --driver docker-container ... --use` — then `scripts/engine_image.py::_buildx()`
running `docker buildx inspect default` (the legacy docker-driver `default` builder
exists on the runner) and prepending `--builder default`. The docker driver can READ
a registry cache but cannot EXPORT one, so the privileged `--cache-to
type=registry,...` (added when `LLGENIE_CACHE_WRITE=1`, set by the owner-guarded
engine-build dispatch) failed.

## The answer

`_buildx()` now gates `--builder default` on `not CACHE_WRITE`. When the build intends
a registry cache **export**, it stays on the ACTIVE builder — the `docker-container`
instance `setup-buildx-action` created and `--use`d — which supports the export. When
`CACHE_WRITE` is unset (a fork/PR/local build, which only READS the registry cache),
`--builder default` is still preferred so locally-loaded base images are seen; the
fresh-Colima guard (no default builder -> buildx must not error) is unchanged.

`CACHE_WRITE` is only ever set by the owner-guarded engine-build dispatch, never by a
PR/fork/local build, so the slow non-pushing verifying builds keep preferring `default`
and the GPU cache-warm cells use the container driver.

**measured:** new test `test_a_cache_write_build_stays_on_the_container_builder` FAILS
on the old code (`--builder default` forced) and PASSES on the fix; 167 cache-adjacent
tests pass (engine_skills, ci_images, engine_image_matrix, force_rebuild); lint
linefeed + AST clean.
