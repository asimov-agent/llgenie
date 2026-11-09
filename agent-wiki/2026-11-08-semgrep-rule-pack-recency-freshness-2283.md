# Semgrep rule pack got a recency floor and a negative control (issue #2283)

## The gap

The committed semgrep rules pack was content-pinned (`rules_sha` in `digests.json['semgrep']`,
enforced by `scripts/security_scan.py::check`) but had no recency floor: no `rules_captured_at`, no
`rules_count`, and `SCANNER_BASELINE`/renovate covered only the binary version. A pack frozen at its
2026-11-08 capture would keep `make check-security-scan` green forever while upstream `p/default`
added rules this tree never ran — the #1252/#1262 silently-diverging-pin class, on the rule set that
defines the SAST surface.

Measured at `origin/main@4b01518f`: `digests.json['semgrep']` keys were only
`dockerfile, ref, rules_file, rules_sha, tag, version`; the committed `default.yml` held 1,073 rules.

## The fix (PR #2315)

1. **Recency floor** — `digests.json['semgrep']` records `rules_captured_at` (ISO date the pack was
   last resolved from upstream `p/default`) and `rules_count` (parity target).
   `scripts/security_scan.py::check` fails `make check-security-scan` when `rules_captured_at` is
   absent, is not an ISO date, or is older than `RULES_BASELINE_DAYS = 30`, and when `rules_count` is
   absent. A pack captured more than 30 days ago reds the gate.
2. **Refresh-path half** — `scripts/scanner_image.py::write` (the `make scanner-digests` re-pin) now
   stamps `rules_captured_at = today` and `rules_count` alongside `rules_sha` whenever the pack is
   re-captured, so a re-capture authoritatively resets the floor.
3. **Negative control** — tests prove an aged pack (`rules_captured_at: 2020-01-01`) reds the gate
   naming the 30-day baseline, a missing `rules_count` reds, and the current pack is green. Widening
   `RULES_BASELINE_DAYS` or dropping `rules_count` is what the control catches.

## The gap is already live

Resolving the pinned image's `p/default` (`ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`) at
`origin/main` prints `found 0 configuration error(s), and 1074 rule(s)` — the committed pack is
already 1 rule behind upstream. The re-pin folding in the 1074th rule (and the automated renew/release
that opens the re-pin PR) stays open on #2283; `rule-set-freshness.md` notes `p/default` cannot be
dumped byte-exact, so that half is a design decision.
