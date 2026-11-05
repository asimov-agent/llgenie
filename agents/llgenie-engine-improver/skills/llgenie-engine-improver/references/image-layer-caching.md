# Engine image layering: what is cached vs recompiled

Answer "is the base rebuilt / can we just reuse a Docker Hub image?" from these facts, not intuition.

## The base IS an official upstream image, wrapped and cached

`containers/engines/base/Dockerfile.<arch>` each do `FROM <official upstream>` plus the build
toolchain (`ca-certificates curl git build-essential cmake ninja-build zstd python3 tar` and
`uv 0.9.5` copied from `ghcr.io/astral-sh/uv`):

| base tree tag | FROM (upstream registry) |
|---|---|
| `llgenie/base-cuda:<hash>` | `nvidia/cuda:13.0.2-devel-ubuntu24.04` |
| `llgenie/base-rocm:<hash>` | `rocm/dev-ubuntu-24.04:7.0-complete` (AMD) |
| `llgenie/base-cpu:<hash>` | `ubuntu:24.04` |

Each base is built ONCE (`make build-engine-base BACKEND=<arch>`, CI: `engine-base` job), pushed,
and reused by every compiled engine. It is **not** rebuilt per engine — in a build log the base
resolves in ~0.1s and `apt-get`/`WORKDIR` steps print `CACHED`:

```
#7 FROM docker.io/llgenie/base-cuda:79cfaf25ba@sha256:...  0.1s DONE
#8 RUN apt-get install ... python3-dev                      CACHED
```

## The long pole is the engine's OWN source compile, on top of the base

`containers/engines/dockerfiles/<engine>/Dockerfile.<arch>` start `FROM llgenie/base-<arch>:<hash>`
then run `engine_runner.py install params.json` — a wheel download plus a **source compile of the
engine's native extensions** (e.g. vllm v0.33.0: ~17 CUDA native extensions — flash-attn, fa3/fa4,
flashmla, deep_gemm — against `LLGENIE_CUDA_ARCH` sm list, or the ROCm gfx list). That compile is
unavoidable, happens once per engine, and happens in CI too. Do not describe it as base-image work.

## Reuse gate: the registry buildcache tag

`scripts/engine_image.py::_buildx` builds with
`--cache-from type=registry,ref=<REGISTRY>/<repo>:buildcache-<variant>` and caches to the same ref.
If that tag does not exist yet, buildx logs
`failed to configure registry cache importer: .../buildcache-cuda: not found` and the engine layer
recompiles from scratch — this is the FIRST build of a variant, not a fault. Once a green CI run
publishes `buildcache-<variant>`, later builds (local and CI) reuse the compiled layer in seconds.
The image tag itself hashes four inputs: variant params, committed Dockerfile, `containers/engines/entrypoint.sh`,
`scripts/engine_runner.py` — classify drift by which of the four moved.

## MAX_JOBS=2 is a CI memory guard, not a host tuning

The install step carries `MAX_JOBS=2 CMAKE_BUILD_PARALLEL_LEVEL=2` inline (the #1558 fix for the
16 GiB CI runner OOM). On a big host this throttles hard (e.g. 32-core RTX-4090 box at loadavg ~5).
An outer exported `MAX_JOBS` will NOT override it: the value is inline in the literal step string, so
raising it requires a params edit + `make generate-engine-params` + a fresh build (loses elapsed
progress). Letting the CI-matching build finish is the default; a host-speed rebuild is a deliberate trade.
