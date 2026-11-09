# Give the committed semgrep rule set a recency floor (issue #2283)

## Why

The committed semgrep pack is content-pinned (`semgrep.rules_sha` in digests.json) but has no
recency floor: no `rules_captured_at`, no `rules_count`, and the engine `SCANNER_BASELINE`/renovate
floor covers only the binary version. A pack frozen at its 2026-11-08 capture passes
`make check-security-scan` green forever while upstream `p/default` adds rules this tree never runs.

## What changes (task checklist)

- [ ] `scripts/security_scan.py`: declare `RULES_BASELINE_DAYS` (a number) and fail
      `make check-security-scan` when `semgrep.rules_captured_at` is absent, is not an ISO date, or
      is older than the recency floor; fail when `semgrep.rules_count` is absent.
- [ ] `containers/scanners/digests.json`: record `semgrep.rules_captured_at` and `semgrep.rules_count`.
- [ ] `scripts/scanner_image.py::write` (`make scanner-digests`): stamp `rules_captured_at = today`
      and `rules_count` beside `rules_sha` on re-pin, so a re-capture resets the floor.
- [ ] Tests: negative control (an aged pack reds the gate naming the baseline), a missing
      `rules_count` reds, and the current pack is green.
- [ ] Docs: agent-wiki note + changes.d fragment; renovate/scheduled re-capture of `p/default` is
      the still-open design half (rule-set-freshness.md).
