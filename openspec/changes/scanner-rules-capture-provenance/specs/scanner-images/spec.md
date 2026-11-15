## ADDED Requirements

### Requirement: The rules capture date is identity-checked on the rules hash

`scripts/scanner_image.py::write()` MUST stamp `semgrep.rules_captured_at` in
`containers/scanners/digests.json` with the current date ONLY when the rules pack actually moved —
i.e. the recomputed `rules_sha` differs from the committed one, or no capture was ever recorded.
When the recomputed `rules_sha` equals the committed one, the previously recorded
`rules_captured_at` MUST survive the rewrite unchanged, so the date stays evidence about the pack
and not about the last `make scanner-digests` invocation.

#### Scenario: an unchanged pack keeps its capture date across a rewrite

- **Given** a fixture tree whose `digests.json` records a `semgrep` pack captured on an earlier
  date, and whose rules pack is unchanged
- **When** `scripts/scanner_image.py::write()` runs again
- **Then** the entry keeps the earlier `rules_captured_at` and the same `rules_sha`

- **Test:** `tests/test_scanner_images.py::test_rewriting_an_unchanged_rules_pack_keeps_the_capture_date`

#### Scenario: a changed pack is stamped as a new capture

- **Given** a fixture tree whose `digests.json` records an earlier capture date
- **When** a rule is added to the pack and `write()` runs
- **Then** the new `rules_sha` is recorded and `rules_captured_at` is today's date

- **Test:** `tests/test_scanner_images.py::test_a_changed_rules_pack_advances_the_capture_date`
