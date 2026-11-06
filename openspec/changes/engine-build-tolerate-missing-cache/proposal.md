# engine-build-tolerate-missing-cache

## Why

The default `make engine-build` sweep (`engine="" arch=""`, issue #1842) is red on the
`engine-build-tensorfold-cuda` cell (run `42192579462` @ `4c3ac6f7`, job `127808054688`
`engine-build-tensorfold-cuda` failed, 26/27 other jobs success). The cell's
`--cache-from type=registry,ref=ghcr.io/asimov-agent/llgenie/tensorfold:buildcache-cuda` at
`scripts/engine_image.py::_buildx()` **hard-fails the whole build with `manifest unknown`**
when the cache image has never been seeded — a cold cache is a TIME cost that must never be a
**red cell**. This single red is what blocks AC4 of #1836 ("the default sweep is green").

## What changes

`engine_image.py::_buildx()` gets a new helper `_cache_read_args(cache_ref)` that probes the
registry cache ref with `docker buildx imagetools inspect` **before** adding
`--cache-from type=registry`. When the image exists the read is unchanged (layers reused);
when it is absent the build proceeds **cold** (no `--cache-from`) — a recorded decision (printed
note, issue #1796), never a silent skip. The privileged write (`--cache-to`) is untouched: the
first cold build seeds the cache for the next run. Both the local read path and the push path use
it. No gate weakening, no tensorfold source edits, no workflow-login change.

## Out of scope

- The `LLGENIE_CACHE_WRITE`/GHCR-login mismatch itself (the anonymous-token 403 class) — that is
  the separate #1440-class work; this change makes the read-side `manifest unknown` a cold build
  rather than a red cell.
- Any change to what the gate checks, tensorfold sources, or workflow login gating.
