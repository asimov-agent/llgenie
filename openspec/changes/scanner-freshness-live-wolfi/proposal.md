# Scanner freshness gate compares against the live Wolfi index, not a frozen dict (issue #2709)

## Why

`make check-security-scan`'s freshness floor (issue #1284) compares `containers/scanners/digests.json`
against `SCANNER_BASELINE` — a hardcoded dict last re-measured 2026-11-07. It never asks Wolfi what it
publishes today, so a pin that lags upstream reads green because the gate compares it to the same stale
floor. Measured at main `6a56fc94`: Wolfi had already moved grype to `0.121.3-r2` while the gate was
self-consistent against the `0.121.2-r1` it compared itself to — the exact silent lag the gate exists to
prevent, hidden inside the gate's own staleness. A freshness floor that only checks itself is not a floor.

## What changes (task checklist)

- [ ] Add a live-Wolfi freshness gate to `scripts/security_scan.py`: a `freshness` command that fetches
      the x86_64 APKINDEX (no credential), parses the newest published build per pinned scanner package,
      and fails, naming the package / pinned version / live newest version, when a pin is not the newest
      the index publishes — printing the index snapshot date it measured against.
- [ ] Wire the live gate into the scheduled security lane (`security-scan.yml`), folded into the
      run's final exit step (the scan, issue-filing and bump PR all still happen; a pin lag reddens the
      run last, never aborting mid-pipeline), and give it a `make check-security-freshness` target.
- [ ] Keep the hermetic `make check-security-scan` network-free and green at main; `SCANNER_BASELINE`
      stays as the human-readable record while the live index drives the freshness verdict.
- [ ] Tests: a stale pin against a fixture index reds with the package/pinned/newest + snapshot date;
      matching pins are green; the `freshness` command fetches a local fixture index.
- [ ] Docs: SCANS.md table row, an agent-wiki note + CHANGES.md index row.
