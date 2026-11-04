# 2026-11-04 engine-build cache write-back (#1694)

The `engine-build.yml` sweep reads a registry layer cache on every fresh `ubuntu-latest` runner
but never writes it back on a build-and-verify run, so each cell stays cold run over run
(the #1694/#1568 class). This note records the verdict-independent half of the fix: the
cache-write gate, landed always; the matrix-aware timeout/targets half is decided by the
#1696-head measurement and recorded separately when it lands.

## Measured before / after

- Before: `scripts/engine_image.py::_buildx` non-push branch passed `--cache-from
  type=registry,ref=<name>:buildcache` but no `--cache-to` (lines 205-206 at `9ca3a5f4`); a
  `push=false` engine-build cell read a cold cache, compiled, published nothing back, so the
  next run recompiled from scratch.
- After: the non-push branch appends `--cache-to type=registry,ref=<cache_ref>,mode=max`
  **only when `LLGENIE_CACHE_WRITE=1`** — an env the owner-guarded engine-build.yml build job
  sets (`packages: write`, logs into GHCR). A PR/fork/local runner never sets it and stays
  strictly read-only, so the privileged write is never reachable from a fork head (issues
  #155/#638; security-lane scope).

## Verification

- `tests/test_engine_force_rebuild.py::test_a_nonpush_unforced_build_writes_back_the_cache_only_when_privileged`
  drives `_buildx` with and without the flag: without it `--cache-to` is absent (the
  pre-#1694 read-only behaviour); with it `--cache-from` and `--cache-to ...mode=max` are both
  present. `11 passed in 0.05s`.
- `make check-workflows check-actions check-engine-params check-engine-source` green at
  branch head.

## Behaviour note

This does NOT make a first cold rocm compile pass 240 min (cache has nothing warm to reuse on
run one); it makes the SECOND run of a completed cell warm. The first-completion decision is
the #1696 arch-trim measurement; this half is orthogonal and safe to land under the moving
engine tree.

Record: `fix/1694-cache-to` → PR closing #1694 only when the timeout/target half lands with it
(or its own PR; the two halves share the issue). Docs-of-record rows here and in
`docs/BOTS.md`/`CHANGES.md`.
