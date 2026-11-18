# ci-images-cache-ref-content-keyed

## Why

`scripts/ci_images.py::cache_ref` returns the FIXED ref `<registry>/llgenie/<name>:buildcache` for
the CI helper-image lanes (agent image, test image, openspec image). The ref carries no content
hash, so a helper-image Dockerfile or context change replays against a content-unrelated cache
namespace — the exact defect class #2891 fixed for the engine cells and bases, left here as the
remaining fixed-name ref (came from #2891's PR). A stale fixed namespace means either the new
content silently replays old layers or the warm cache is missed entirely, and "what content is this
cache for" is unanswerable from the ref name.

## What changes

`cache_ref(name, root)` derives the cache ref from the same content identity the helper-image tag
already computes (`tag(name, root)`, the Dockerfile + context hash), appending the `-buildcache`
suffix: `<registry>/llgenie/<name>:<12-hex>-buildcache`. `publish` and `_buildx_push` pass the build
root through so the cache namespace always matches exactly the content being built. Build and push
policy is untouched — only the namespace derivation changes.

## Out of scope

- Cache WRITE policy for helper images (unchanged — the #1694/#155 owner-guard stands).
