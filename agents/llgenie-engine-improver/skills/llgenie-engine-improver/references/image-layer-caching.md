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

## `--cache-to` only exists on a `docker-container` driver — gate on the DRIVER, never assume

A registry cache WRITE (`--cache-to type=registry,…`) is a buildx capability of the selected builder's
driver, not a flag you can always pass. On the classic `docker` driver buildx aborts the whole build at
the export step after minutes of real compile:

```
ERROR: failed to build: Cache export is not supported for the docker driver.
Switch to a different driver, or turn on the containerd image store, and try again.
```

The trap that produced it: `engine_image.py::_buildx` probes `docker buildx inspect <builder>` and, if the
`default` builder EXISTS, appends `--builder default`. On an ubuntu GHA runner a `default` builder always
exists and it is the classic docker driver — so even when `setup-buildx-action` created and `--use`d a
capable `docker-container` builder (`Driver: docker-container`, `"Cache export": true` in its inspect
output), the forced `--builder default` discards it and the cache write reds. A fresh Colima/macOS host
has no `default` builder, so the flag is omitted and buildx falls back to the active (docker-container)
builder — which is why the same code reds on Linux CI and works elsewhere.

Rule: append `--cache-to` **only when the driver of the builder actually selected for the build is
`docker-container` (or containerd image store)**; otherwise log a one-line documented skip and let the
build stay read-only. Never infer capability from `setup-buildx-action` having run, and never infer it
from the builder the action `--use`d — probe the builder you name.

**`docker buildx inspect` does not support `--format`** on every buildx build (it errors); parse the
`Driver:` line out of the default table output instead:

```python
def _buildx_driver(builder: str) -> str:
    out = subprocess.run(["docker", "buildx", "inspect", builder],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.strip().startswith("Driver:"):
            return line.split(":", 1)[1].strip()
    return ""
```

**Pick the builder that is ACTIVE, not `default`.** `default` is a builder *name*, not a capability — on a GHA runner it exists and is the classic docker driver, so "name `default` when the caller names none" re-introduces the exact bug the gate was meant to stop. Selection order for an unnamed builder:

1. the row marked `*` in `docker buildx ls` (that is what a plain `docker buildx build` would use, i.e. the builder `setup-buildx-action` created and `--use`d);
2. only if no `*` row is findable, fall back to `default` (or omit the flag).

```python
def _buildx_active() -> str:
    out = subprocess.run(["docker", "buildx", "ls"], capture_output=True, text=True).stdout
    for line in out.splitlines()[1:]:
        m = re.match(r"\s*(\S+)", line)
        if m:
            name = m.group(1)
            if "*" in line.split()[0:2] or name.endswith("*"):
                return name.rstrip("*")
    return "default"
```

Abbreviated rows (`default *  docker`) and long-name rows can put the `*` on either of the first two tokens — check both, and strip it from the returned name. Then feed that name into `_buildx_driver()`. Never `inspect <builder> <builder>`: resolve the name ONCE, then pass it.

The two halves are one change, not two: **active-builder selection** decides *which* builder, the **driver gate** decides *whether* `--cache-to` is legal. A fix that only gates on the driver of a forced `default` still loses the warm cache on capable runners (the capable builder is never selected), and a fix that only selects the active builder still reds if the active one happens to be classic. Ship both together. Verify the gate against the real binary, not a mock:
`_buildx_driver("default")` → `'docker'` → SKIP on a GHA runner; a `docker-container` builder → WRITE.
`tests/test_engine_image_matrix.py` is the regression suite for `engine_image.py` (21 tests) — run it at
any change to `_buildx` before pushing.

## MAX_JOBS=2 is a CI memory guard, not a host tuning

The install step carries `MAX_JOBS=2 CMAKE_BUILD_PARALLEL_LEVEL=2` inline (the #1558 fix for the
16 GiB CI runner OOM). On a big host this throttles hard (e.g. 32-core RTX-4090 box at loadavg ~5).
An outer exported `MAX_JOBS` will NOT override it: the value is inline in the literal step string, so
raising it requires a params edit + `make generate-engine-params` + a fresh build (loses elapsed
progress). Letting the CI-matching build finish is the default; a host-speed rebuild is a deliberate trade.
