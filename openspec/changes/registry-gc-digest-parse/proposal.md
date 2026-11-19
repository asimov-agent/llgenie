# Registry GC digest parse fix (issue #2924)

## Why

`make registry-cache-gc` — the human-side sweep shipped by #2914 — cannot delete any orphan it
lists. Measured on main `c564764c5645` (2026-11-19): `docker buildx imagetools inspect` aligns the
digest line as `Digest:    sha256:c5299a41…` (colon + padding spaces), while
`registry_cache_orphans.digest_of()` accepts only a line starting exactly `digest: sha256:` (single
space). All 8 orphans fail with `no digest for …`, rc=2, `deleted 0; remaining verified orphans: 8`.
The unit tests inject `digest_resolver`, so the real parser was never exercised against the tool's
only real-world output format. #2914 AC2 (the tags actually gone) and #2923's zero-orphan acceptance
both block on this parse.

## What Changes

- `scripts/registry_cache_orphans.py`: the exact-prefix line scan in `digest_of` is replaced by a
  module-level tolerant regex `digest:\s*(sha256:[0-9a-fA-F]{16,})` (case-insensitive), consulted
  through an extracted `_extract_digest(ref, text)` so the parser sits behind a testable seam; the
  no-digest `SystemExit` wording is unchanged.
- `tests/test_registry_cache_orphans.py`: update-not-add — the injected-resolver tests stay, and new
  cases drive the REAL `digest_of` through a monkeypatched `run_ok` with the imagetools output
  captured verbatim from GHCR (padded alignment), the legacy single-space line, and a no-digest
  refusal.

## Impact

- Affected specs: `registry-cache-gc` (new capability requirement: digest extraction must accept
  the registry tool's real padded output)
- Affected code: `scripts/registry_cache_orphans.py`, `tests/test_registry_cache_orphans.py`
- After merge: the sweep runs once, stamped on #2914, closing its AC2 with the zero-orphan re-measure.
