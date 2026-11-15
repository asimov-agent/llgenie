# scanner-digests-capture-date

## ADDED Requirements

### Requirement: the semgrep rules capture date tracks the rules pack, not the write

When `scripts/scanner_image.py::write` rewrites `containers/scanners/digests.json` and the
recomputed `semgrep.rules_sha` equals the prior committed entry's `rules_sha`, the committed
`semgrep.rules_captured_at` MUST be carried forward unchanged — `write` MUST NOT stamp
`datetime.date.today()`. `write` MUST stamp today only when the recomputed `rules_sha` differs from
the prior entry's, or when no prior `semgrep` entry exists. An unchanged `rules_file`,
`rules_count`, and the carry-forward of `image_digest` for an unchanged tag all keep their existing
behaviour.

#### Scenario: an unchanged rules pack keeps its committed capture date

- **Given** a committed `containers/scanners/digests.json` whose `semgrep` entry records
  `rules_sha` equal to the current pack's content hash and `rules_captured_at` = `2026-11-08`
- **When** `make scanner-digests` runs `write()` and the rules pack is byte-identical
- **Then** the rewritten entry preserves `rules_captured_at` = `2026-11-08` and the same
  `rules_sha` (measured defect: a re-run had advanced the date to `2026-11-15` unchanged)
- **Test:** `tests/test_scanner_images.py::test_rewrite_keeps_rules_captured_at_for_an_unchanged_pack`

#### Scenario: a changed rules pack advances the capture date to today

- **Given** a committed `containers/scanners/digests.json` whose `semgrep` entry records a
  `rules_sha` that does not match the current pack (the pack has since been re-captured)
- **When** `make scanner-digests` runs `write()` over the changed pack
- **Then** the rewritten entry stamps `rules_captured_at` = today and records the new `rules_sha`
- **Test:** `tests/test_scanner_images.py::test_rewrite_advances_rules_captured_at_for_a_changed_pack`

#### Scenario: a first capture stamps today

- **Given** a tree whose `digests.json` has no prior `semgrep` entry (or no prior entry at all)
- **When** `write()` runs with a rules pack present
- **Then** it stamps `rules_captured_at` = today beside the freshly computed `rules_sha`
- **Test:** `tests/test_scanner_images.py::test_rewrite_stamps_first_capture_today`
