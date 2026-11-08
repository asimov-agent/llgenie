# Give the committed semgrep rule set a recency floor

- [x] `scripts/security_scan.py`: `RULES_BASELINE_DAYS` constant + `check()` fails when
      `semgrep.rules_captured_at` is absent, non-ISO, or older than the recency floor, and when
      `semgrep.rules_count` is absent.
- [x] `containers/scanners/digests.json`: record `semgrep.rules_captured_at` and `semgrep.rules_count`.
- [x] `scripts/scanner_image.py::write` (`make scanner-digests`): stamp `rules_captured_at = today`
      and `rules_count` beside `rules_sha` on re-pin.
- [x] Tests: negative control (aged pack reds), missing `rules_count` reds, current pack green.
- [x] Docs: agent-wiki note + changes.d fragment; the automated re-capture of `p/default` stays open
      as the design half (rule-set-freshness.md).
