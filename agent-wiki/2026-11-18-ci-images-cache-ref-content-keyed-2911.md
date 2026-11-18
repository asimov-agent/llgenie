# CI helper-image buildx cache refs keyed to content (issue #2911)

Implements issue #2911: `scripts/ci_images.py::cache_ref` returned the FIXED ref
`<registry>/llgenie/<name>:buildcache` for the CI helper-image lanes (agent / test / openspec), so a
Dockerfile or context change replayed against a content-unrelated cache namespace — the defect class
#2891 already fixed for the engine cells and bases, left here as the remaining fixed-name ref.

## What was built (verified against OpenSpec change `ci-images-cache-ref-content-keyed`)

- `scripts/ci_images.py::cache_ref(name, root)` derives the ref from the same content identity the
  helper-image tag already computes — `tag(name, root)`, the Dockerfile + context hash — appending
  the `-buildcache` suffix: `<registry>/llgenie/<name>:<12-hex>-buildcache`. `publish` and
  `_buildx_push` pass the build root through, so the cache namespace always matches exactly the
  content being built.
- `tests/test_ci_images.py::test_cache_ref_is_keyed_to_the_image_content` proves unchanged content
  replays the same namespace and a changed lockfile moves it (one namespace per content). The two
  publish tests now assert the content-keyed ref (`<hash>-buildcache`) on both `--cache-from` and
  `--cache-to`.

## Decisions

- The cache namespace follows the image content hash — one namespace per content, never a shared
  fixed name. Build/push and cache WRITE policy (the #1694/#155 owner-guard) are untouched; only the
  namespace derivation changed, per the issue's acceptance.

## Current status

Change sits uncommitted in the implementation leg. `tests/test_ci_images.py` passes (42 tests),
`openspec validate ci-images-cache-ref-content-keyed` is green (CLI 1.10.0 — the docker daemon is
unavailable in the implementation container, so the make seam could not run), `make changes-index`
rewrote `CHANGES.md`. The full loop/CI gates run in the pipeline where the docker daemon exists.
