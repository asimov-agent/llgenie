# 2026-11-15 — rules-capture provenance (issue #2713)

OpenSpec change: `scanner-rules-capture-provenance`. Branch `feat/2713-rules-capture-provenance`,
PR opened against upstream main closing issue #2713.

## Verified against the spec

- `scripts/scanner_image.py::write()` now reads the prior `digests.json` before stamping:
  `semgrep.rules_captured_at` survives a rewrite while the recomputed `rules_sha` equals the
  committed one; only a moved (or never-recorded) pack is stamped with today. Matches the ADDED
  requirement in `openspec/changes/scanner-rules-capture-provenance/specs/scanner-images/spec.md`.
- Regression pair: `tests/test_scanner_images.py::test_rewriting_an_unchanged_rules_pack_keeps_the_capture_date`
  and `::test_a_changed_rules_pack_advances_the_capture_date` — 24 passed in that module locally
  (fixture `_semgrep_tree` carries a semgrep scanner + rules pack).
- Measured defect (from the #2707 verification, main `6a56fc94f0`): a grype-only Dockerfile change
  moved `rules_captured_at` 2026-11-08 → 2026-11-15 with `rules_sha` byte-identical. The keep is
  identity-checked on `rules_sha`, so that rewrite is now a no-op for the date.

## Key decisions

- The keep is keyed on `rules_sha` equality only — no fuzzy "pack looks similar" logic; a changed
  pack always re-stamps, so the refresh lane's `rules_captured_at == refresh date` invariant
  (issue #2283) is untouched.
- The recency-floor value (`RULES_BASELINE_DAYS = 30`, issue #1284) was not changed — this fix is
  strictly about *who may move the date*.

## Current status

Branch `feat/2713-rules-capture-provenance` from `origin/main` (`1314a25241`); local gates green
(check-scanner-images, check-security-scan, check-wiring, openspec-validate).
