# make scanner-digests keeps the semgrep capture date when the rules pack is unchanged

This change implements the issue filed from the #2707/#2708 verification (marker
`rules-captured-at-silent-advance`); #2707 is the verification that exposed the silent drift,
and #2708 is the sibling tracking issue that verification filed.

## Why

`scripts/scanner_image.py::write()` (the body of `make scanner-digests`) rewrites
`containers/scanners/digests.json` and unconditionally stamps `semgrep.rules_captured_at` to
`datetime.date.today()`. Running the target for an unrelated reason (e.g. a grype pin refresh)
advances the semgrep rules-pack capture date even though
`containers/scanners/semgrep/rules/default.yml` did not change. Measured on 2026-11-15 while
verifying #2707: `make scanner-digests` moved `rules_captured_at` from `2026-11-08` to
`2026-11-15` with `rules_sha` byte-identical; the #2707 branch had to revert the field by hand.

`rules_captured_at` is the recency evidence the scan gates read (issue #1284's rules-recency
floor). A date that advances with any write makes a stale rules pack look freshly captured: the
gate's memory of WHEN the pack was last refreshed stops being evidence about the pack. Silent data
drift inside a pinned manifest also produces spurious diffs in every PR that legitimately re-runs
the target.

## What Changes

1. **The capture date tracks the pack, not the write.** `write()` reads the committed record
   before rewriting and keeps the prior `rules_captured_at` whenever the recomputed `rules_sha`
   equals the prior entry's `rules_sha`. It stamps today only when `rules_sha` actually changed,
   or when there is no prior entry at all. (The committed record is already read for the
   `image_digest` carry-forward, so this reuses one read of `digests.json`.)
2. **A regression test pair.** `tests/test_scanner_images.py` proves both directions with a
   fixture tree + committed record: unchanged pack + rewrite preserves the date; changed pack +
   rewrite advances it to today.

## Impact

- Affected specs: `scanner-digests-capture-date` (ADDED requirement)
- Affected code: `scripts/scanner_image.py` (`write()`), `tests/test_scanner_images.py`
- Gates unchanged: `make scanner-digests`, `make check-scanner-images` and
  `make check-security-scan` keep their existing behaviour; no job, target, or secret moves. The
  committed `containers/scanners/digests.json` already records the correct `2026-11-08` capture
  for the unchanged pack, so no manifest edit is needed.
