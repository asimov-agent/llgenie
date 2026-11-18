# engine-cache-namespace-2891

## Why

Issue #2891 measured a cold ROCm engine-base build at 45-90+ minutes (run 44143247189, head `8332018901` of #2840: ROCm job still building at 61+ minutes) and four engine PRs re-shipping near-identical ROCm layers 28 times in one day (15 distinct cells needed). The buildx registry layer cache is already wired into the build seam (`scripts/engine_image.py` `_cache_read_args`/`_cache_write_args`, #1694/#1842/#1880/#1915), but the cache refs are FIXED names — `llgenie/base-<backend>:buildcache` and `llgenie/<engine>:buildcache-<variant>` — with no link to the Dockerfile content hashes the base tags already carry (`es.base_tag` = `llgenie/base-<backend>:<sha256[:10]>`). A base bump therefore replays against a stale, content-unrelated cache namespace: the layers a new base could legitimately reuse are indistinguishable from the old base's, the namespace accretes cross-version blobs, and the CI minutes the issue measured keep being paid.

## What Changes

- Key the registry layer-cache refs by the content hashes the tags already carry:
  - base images: `llgenie/base-<backend>:buildcache` → `llgenie/base-<backend>:<basehash>-buildcache` (the digest `engine_skills.base_tag` already computes from the rendered base Dockerfile),
  - engine cells: `llgenie/<engine>:buildcache-<variant>` → `llgenie/<engine>:<tag-hash>-buildcache-<variant>` (the `<basehash>-<cellhash>` pair the published cell tag already embeds).
  A base or cell content change thus starts a NEW cache namespace instead of replaying a stale one; an unchanged replay keeps hitting the same, now content-matched, namespace.
- Add a hermetic proof lane: `tests/test_engine_cache_namespace.py` pins both derivations from rendered content (same content → same namespace; changed content → different namespace), and `make check-engine-cache-namespace` runs it as the repo-visible gate (issue AC 3's "make target proving cache tag tracks the base content hash").
- Update the existing seam tests that hard-code the old fixed `:buildcache` refs.
- Prove AC 1/AC 2 from real engine-build runs on the PR head: a chain run whose buildx log carries the hash-qualified `--cache-to type=registry,ref=...-buildcache` export, and a replayed unchanged ROCm cell concluding under 1200s once the first build has warmed the namespace.

No build-policy change: `LLGENIE_CACHE_WRITE` (owner-guarded dispatch only, #1694/#155/#638) and the `NO_CACHE_EXPORT` docker-driver escape (#1915) are untouched.
