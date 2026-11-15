# Proposal: rules-capture provenance in digests.json

## Why

`scripts/scanner_image.py::write()` stamps `semgrep.rules_captured_at` with today's date on every
`make scanner-digests` run — even when the rules pack hash is unchanged. Measured 2026-11-15 during
the #2707 verification (main tip `6a56fc94f0034c134db23f9ce4dc62011d1d2699` at the time of the run):
rewriting digests.json for a grype-only Dockerfile change moved `semgrep.rules_captured_at`
2026-11-08 → 2026-11-15 with `semgrep.rules_sha` byte-identical (issue #2713).

That date is the recency-floor evidence the security lane reads (issue #1284): it claims *when the
rules pack was captured*. A rewrite that changes nothing and silently advances it makes a stale pack
look freshly captured — the gate's memory stops being evidence about the rules.

## What Changes

- `scripts/scanner_image.py::write()`: `rules_captured_at` becomes identity-checked on `rules_sha` —
  the committed capture date is kept while the recomputed `rules_sha` equals the committed one, and
  only a pack that actually moved (or was never recorded) is stamped with today.
- `tests/test_scanner_images.py`: `_semgrep_tree` fixture + pair of regression tests — the keep on
  an unchanged pack, the advance on a changed pack.

## Out of Scope

- The recency-floor *value* and how `check-security-scan` consumes `rules_captured_at` (issue #1284)
  are unchanged; this fixes only who is allowed to move the date.
