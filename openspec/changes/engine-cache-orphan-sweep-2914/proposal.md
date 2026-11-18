# engine-cache-orphan-sweep-2914

## Why

The buildx registry layer-cache namespaces for helper images and engine bases/cells used to be
FIXED names (`llgenie/<name>:buildcache`, `llgenie/base-<backend>:buildcache`,
`llgenie/<engine>:buildcache-<variant>`) with no link to the content being built, so a base or
engine-content bump replayed the layer cache against a stale, content-unrelated namespace. The
cache-keying changes (#2891 / PR #2912, and #2911 / PR #2915) make every build write a
CONTENT-HASH-keyed namespace instead (`<...>-buildcache`). The old fixed tags remain in GHCR as
orphaned cache layers: they keep consuming registry storage and quota, and a future reader seeing
`test:buildcache` in old logs could mistake it for a live ref.

The two keying changes are NOT yet on `main` — so at the head this change is written against, the
fixed names are still LIVE producers. An actual registry deletion now would destroy the cache the
current builds still read and write. That is exactly why the sweep is gated: it is safe only once
both keying changes land.

## What changes

A new audit + sweep tool (`scripts/cache_orphan_report.py`) and two make targets.

- `make engine-cache-orphan-report` (or `list`) — enumerate the fixed-name cache tags present in the
  org's `llgenie/` container packages (via `gh api`), and print those **no producer seam still
  writes**. The "live producer" set is derived from the ONE seams the builds call
  (`engine_image.cache_ref`, `ci_images.cache_ref`), so the report is correct at every head: while
  keying has not landed the seams still return the fixed names and the report prints zero orphans;
  the moment the keying changes land the same seams return content-keyed names and the superseded
  fixed tags surface as orphans — no second derivation to keep in sync.
- `make engine-cache-orphan-sweep` — delete those orphans via the registry API, gated by the same
  live-producer check: a live fixed tag is never proposed for deletion.

The two producer call sites in `scripts/engine_image.py` gain an explicit ONE-seam `cache_ref` that
`build_base`/`build` call (behavior-identical today; the keying PRs edit this single function).

## Out of scope

- The cache-keying changes themselves (#2891 / PR #2912, #2911 / PR #2915) — separate, open PRs;
  this change only ships the GC tooling that becomes meaningful once they land.
- Actually running the sweep in this change: that deletes live cache at this head, which the issue
  itself says to do only after both keying PRs land on `main`.
