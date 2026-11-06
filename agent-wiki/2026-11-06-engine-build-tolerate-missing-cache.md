# A never-seeded registry cache builds cold, not red

## Background (measured 2026-11-06)

The default `make engine-build` sweep (`engine="" arch=""`) was red on its
`engine-build-tensorfold-cuda` cell (run **42192579462** @ `4c3ac6f7`, job **127808054688**
failed, 26/27 other jobs success — issue #1842). That cell is untouched by the #1837 diff
(`DEFAULT_CPU_ONLY = {"vllm"}`), so the red pre-dates it and blocks AC4 of #1836 independently.

`scripts/engine_image.py::_buildx()` appends `--cache-from type=registry,ref=ghcr.io/
asimov-agent/llgenie/tensorfold:buildcache-cuda` (L220, read path) on every unforced build.
On a **fresh runner the cache image has never been seeded** (`tensorfold:buildcache-cuda` was
"manifest unknown") — and buildx `--cache-from type=registry` **hard-fails the WHOLE build**
with `manifest unknown` in that case. A cold cache is a TIME cost (the fresh build compiles the
layers) that must never be a **red cell**.

## The answer

`_buildx()` now goes through a new helper `_cache_read_args(cache_ref)`:

1. probe `docker buildx imagetools inspect <cache_ref>` — the same manifest GET the import
   would issue, run through the existing `_sh` seam;
2. if the image **exists** → return exactly `["--cache-from", "type=registry,ref=..."]`
   (unchanged layer reuse);
3. if it is **absent** → return `[]` and print `[engine-image] registry cache <ref> absent ->
   cold build (cache read skipped; #1842)` — a recorded decision (#1796), never a silent skip.

The privileged write (`--cache-to`) is untouched: the first cold build seeds the cache for the
next run. `force=True` still passes `--no-cache` and no read; the push path and the
`--builder default` selection are unchanged. No gate weakening, no tensorfold source edits, no
workflow-login change.

**measured:** new tests `test_a_missing_cache_image_builds_cold_not_red` (absent cache → no
`--cache-from`, `--cache-to` still seeds when `CACHE_WRITE=1`) and
`test_a_present_cache_image_keeps_cache_from` (present cache → read unchanged); existing
force/push cases and `test_engine_skills.py::test_push_targets_only_the_registry_tag` (now
locates the build argv by `--push`, robust to the new probe call) all green — 183 passed across
force_rebuild / image_matrix / ci_images / engine_skills / engine_binary_flags; check-docs,
changes-index, lint green.
