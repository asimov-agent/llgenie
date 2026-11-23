# cache-write-package-probe

## Why

The content-keyed layer-cache refs introduced by PR #2912 (issue #2891) have never been seeded on
GHCR, because the WRITE side shares the READ side's probe of the cache ref itself. Measured on live
post-#2912 builds:

- run `44404039696`, job `135154515704` (2026-11-18, edge0-cuda, 2872 s):
  `[engine-image] registry cache ghcr.io/asimov-agent/llgenie/edge0:4a7964de-874f7c96-cuda-buildcache absent -> cold build (cache write skipped; #1880)`
- run `44925052309`, job `136909270729` (2026-11-21, edge0-cuda, 2868 s): the identical skip line.

The registry confirms nothing was ever exported: `asimov-agent/llgenie/edge0` carries the tags
`4a7964de-16ec5d83-cuda, cuda, latest, 4a7964de-874f7c96-cuda` (no `-buildcache`), and
`asimov-agent/llgenie/base-rocm` carries only `17779d5326`. The skip is structural: `_buildx` probes
`_cache_exists(cache_ref)` ONCE (`scripts/engine_image.py:293`) and threads that one result into
`_cache_write_args` (`scripts/engine_image.py:239-262`), so a missing cache ref — the exact state
that needs seeding — is read as #1880's "the engine's package is not on the registry yet" and the
write is skipped on EVERY build. A namespace whose cache was never seeded can never seed: the probe
only ever returns true for a cache that already exists. The docstring's promise ("The cache is
seeded as soon as the engine's package exists on the registry") has no implementing probe.
Issue #3017.

## What Changes

- `scripts/engine_image.py` gets a package-existence probe `_package_published(cache_ref)` beside
  `_digest_http`: anonymous GHCR pull-token exchange, then `GET /v2/<package>/tags/list?n=1`. A
  non-empty tags list means the package exists and buildx can create the cache tag under it; an
  absent/empty package or an unreachable registry means "not published".
- `_cache_write_args` becomes a write-eligibility ladder instead of one probe:
  1. cache ref exists → `--cache-to type=registry,ref=<ref>,mode=max` (today's behaviour);
  2. cache ref absent AND package published → the same `--cache-to` (the seeding case today missing),
     with the printed note `absent -> seeding it (package published)`;
  3. cache ref absent AND package absent → no `--cache-to`, the existing `cache write skipped; #1880`
     note (the hard-`not found` case the tolerance exists for).
- The single-probe contract (#1880) survives: the package probe is consulted only when a write is
  actually being decided AND the cache ref is absent, at most once per build.
- The read side (#1842) is unchanged: absent cache ref → no `--cache-from`; present cache ref → reads
  as today.
- Tests: the existing #1842/#1880 tolerance tests stub the new package probe as absent (their intent
  — package absent — stays pinned), and new hermetic tests pin the seeding decision on the push
  branch and the `CACHE_WRITE=1` local branch, plus the probe's own token/tags contract.

## Out of scope

- Live proof of the export (a build log showing the cache push at rc=0) and #2891's AC2 warm replay
  under 20 min: those need a live engine-bump wave after this lands and stay tracked on #2891 and
  the live full-matrix sweep issue #3004.
- No build-policy change: `LLGENIE_CACHE_WRITE` (owner-guarded dispatch only) and the `NO_CACHE_EXPORT`
  docker-driver escape (#1915) are untouched. No workflow, no local engine image build.
