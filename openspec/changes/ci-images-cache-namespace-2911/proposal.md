# Proposal: ci-images cache refs keyed to image content

## Why

Issue #2911 (from #2912/#2891). `scripts/ci_images.py::cache_ref` returned the fixed
`llgenie/<name>:buildcache` for every helper image, so every Dockerfile/lockfile change
replayed the buildx registry cache against a namespace unrelated to the content being
built — the same defect class #2891 fixed for engine cells and bases, left in the
helper-image lane.

## What Changes

- `cache_ref(name, root)` returns `llgenie/<name>:<12hex content tag>-buildcache`, reusing
  the exact `tag()` hash the pushed image ref carries: the cache namespace names the content it caches.
- The `publish` cache probe and the `_buildx_push` `--cache-from`/`--cache-to` flags pass the
  repo root through so the ref follows the same inputs as the tag.
- Existing pinned assertions in `tests/test_ci_images.py` move from the fixed name to the
  content-keyed form; a new hermetic test pins the unchanged/changed-content derivation.
- No new Makefile target: the unit suite is discovered, so `make test-unit` gates the new test.

## Impact

- Affected capability: `ci-image-build` (helper-image publish seam)
- Affected code: `scripts/ci_images.py`, `tests/test_ci_images.py`
- Registry effect: the fixed `:buildcache` tags become unused; each content hash gets its
  own `-buildcache` namespace (cold on the first build of that content, warm on replay).
