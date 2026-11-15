# The scanner freshness gate reads the live Wolfi index, not a frozen dict (issue #2709)

## The gap

`make check-security-scan`'s scanner freshness floor (issue #1284) compared
`containers/scanners/digests.json` against `SCANNER_BASELINE` — a hardcoded dict last re-measured on
2026-11-07. It never asked Wolfi what it publishes today, so a pin that lags upstream read green
because the gate compared it to the same stale floor. Measured at main `6a56fc94`: Wolfi had already
moved grype to `0.121.3-r2` while the gate stayed self-consistent against the `0.121.2-r1` it
compared itself to — the pin lag the gate exists to prevent, hidden inside the gate's own staleness.

## The fix (implements issue #2709)

1. **Live comparison** — `scripts/security_scan.py` gains a `freshness` command
   (`make check-security-freshness`): it fetches the public Wolfi x86_64 APKINDEX (no credential,
   urllib + tarfile, a local file stands in for the index in tests), parses every published build,
   and fails, naming the package / pinned version / live newest version, when a pin is not the
   newest the index publishes — printing the index snapshot date it measured against.
2. **Scheduled lane wiring** — the `scan` job in `.github/workflows/security-scan.yml` runs
   `make check-security-freshness` (captured with `continue-on-error`), and the run's final exit
   step reddens the run when either the verdict or the freshness check failed — the day's scan,
   issue-filing and bump-PR work still always runs.
3. **Hermetic gate untouched** — `make check-security-scan` stays network-free and green at main;
   `SCANNER_BASELINE` remains the human-readable record while the live index drives the verdict.

## Verified

- Hermetic: 3 new tests in `tests/test_security_scan.py` prove a stale pin reds a fixture index
  naming the package/pinned/newest + snapshot date, matching pins are green, and the `freshness`
  command fetches a local fixture tarball; the security unit suite is green.
- Live: `python3 scripts/security_scan.py freshness` against the real index reds on the current
  `grype` pin (`0.121.2-r1` -> `0.121.3-r2`, snapshot 2026-11-15) — the gate now surfaces the lag
  the frozen dict hid. Bumping the `grype`/`syft` Dockerfile via `make scanner-digests` + publish +
  pin is a follow-up the gate now forces; this change deliberately does not fabricate an image digest
  for an unpublished tag (issue #2609).

Related findings from the same security-lane audit (#2661): #2706 #2707 #2708.
