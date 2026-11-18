# registry-buildcache-gc-2914 — proposal

Issue: [#2914](https://github.com/asimov-agent/llgenie/issues/2914)

## Why

Two merged changes retired every fixed-name buildx cache namespace this repo wrote to GHCR:

- **#2891 / PR #2912** moved engine cells and bases from `llgenie/<engine>:buildcache-<variant>`
  and `llgenie/base-<backend>:buildcache` to the content-keyed `<full tag>-buildcache`.
- **#2911 / PR #2915** moved helper images from `llgenie/<name>:buildcache` to
  `llgenie/<name>:<12-hash>-buildcache`.

The fixed tags those builds pushed before the switch are still in the registry. Measured against
GHCR at `origin/main` after both merges: **8 orphaned refs** — `test:buildcache`,
`openspec:buildcache`, `agent:buildcache`, `base-cpu|base-cuda|base-rocm|base-vulkan:buildcache`,
and `vllm:buildcache-cpu`. No `cache_ref()` seam in the repo writes those names anymore, so they are
dead layers: they hold storage/quota and make old logs read as if a dead ref were live.

## What Changes

1. **`scripts/registry_cache_orphans.py`** — the sweep tool. `report` enumerates the fixed-name
   cache refs derived from the live repo constants (`ci_images.IMAGES`, `engine_skills.BACKENDS`,
   `engine_image.matrix()` — so a new engine or helper joins the candidate set the moment it enters
   params/), proves each against the registry, and prints the orphans with a count. `gc --yes`
   deletes exactly those versions via the GHCR packages API (version id resolved by digest) and
   re-verifies zero remain.
2. **A delete-guard that cannot touch a live ref**: `ORPHAN_TAG_RE` matches only
   `buildcache` / `buildcache-<variant>`; content-keyed tags (`<pin>-<digest>-<variant>-buildcache`,
   `<12hash>-buildcache`) and any non-cache tag are refused before any delete call.
3. **Two make targets** in `mk/engines.mk`: `registry-cache-orphans` (report) and
   `registry-cache-gc` (explicit deletion only — never wired into any workflow; the main pipeline
   stays tests-only per #2701). The script rides the `scripts/proc.py` subprocess seam.
4. Hermetic tests (`tests/test_registry_cache_orphans.py`): every registry probe is injected —
   no network, no GHCR.

## Out of scope

Nothing further — the sweep is the whole scope of #2914. The registry DELETIONS themselves are a
human-side action after merge (`make registry-cache-gc`), consistent with #746's registry-admin
boundary; CI never performs them.
