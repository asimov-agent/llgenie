# engine-build-cache-write-tolerates-missing-package

## Why

The default `make engine-build` sweep (`engine="" arch=""`, issue #1880) is red on the
`engine-build-tensorfold-cuda` cell (run `42275925732` @ `cf88d285`). The cell's
`--cache-to type=registry,ref=ghcr.io/asimov-agent/llgenie/tensorfold:buildcache-cuda` at
`scripts/engine_image.py::_buildx()` **hard-fails the whole build with `not found`** when the
engine's package does not exist on the registry yet — buildx cannot create a cache ref under a
namespace that is absent. The read side already builds cold when the cache ref is missing
(issue #1842, `_cache_read_args`); the write side does not, so a never-published engine's cell
is red for a reason that is not a build defect.

## What changes

`engine_image.py::_buildx()` gets a new helper `_cache_write_args(cache_ref)` that probes the
registry cache ref with `docker buildx imagetools inspect` **before** adding
`--cache-to type=registry`. When the image exists the write is unchanged (cache seeded for the
next run); when it is absent the build proceeds **cold** (no `--cache-to`) — a recorded decision
(printed note, issue #1796), never a silent skip. Both the local `CACHE_WRITE=1` path and the
push path use it. The read side (#1842) is untouched. The cache is seeded as soon as the
engine's package exists on the registry (a later publish), so the write is only ever skipped for
an engine that has never been published at all.

## Out of scope

- The read-side cache tolerance (#1842) — already landed.
- Any change to what the gate checks, tensorfold sources, or workflow login gating.