# Live scanner freshness: pins judged against the Wolfi index (issue #2709)

Date: 2026-11-15. Branch: `feat/2709-live-scanner-freshness`. Audit origin: #2661 (finding #2709).

## What was verified

- `make scanner-freshness` (`mk/security.mk` → `scripts/security_scan.py freshness`) parses the
  Wolfi x86_64 APKINDEX live (or a local snapshot named by `WOLFI_APKINDEX`) and compares the
  `digests.json` pins (trivy, semgrep, grype) plus the `ARG SYFT_VERSION=` baked into the Grype
  Dockerfile against the newest published build per package. A lag older than
  `FRESHNESS_GRACE_DAYS` (7) fails naming package/pin/live-newest; a package the index lacks fails
  too; an unreadable snapshot is a refusal, never a green.
- Measured live at this commit: grype `0.121.2-r1` lags `0.121.3-r2` and syft `1.57.0-r1` lags
  `1.57.1-r2` — both published 2026-11-14, inside the grace, so the step is green and prints both
  deltas. The bumps themselves belong to #2707/#2708.
- The daily `security-scan.yml` lane runs the step after `check-security-scan`, CAPTURES it
  (`id: freshness`, `continue-on-error`), and raises its outcome only in the lane's LAST step —
  so scans, tagged issues and uploads never get skipped by a stale pin.
- `make check-security-scan` stays hermetic; a test asserts the `check()` body contains no Wolfi
  fetch and no freshness call.
- `tests/test_security_scan.py`: 8 new hermetic tests (fixture APKINDEX stanzas built in
  `tmp_path`, `WOLFI_APKINDEX` override, no network): 57 pass locally.

## Decisions

- Grace keyed on the index's own build timestamps (`t:` fields): Wolfi republishes faster than the
  repo should chase, but a persistent lag goes loud — same discipline as the #2283 rules-age gate.
  A lag with no usable timestamp is treated as out of grace (strict).
- Fixtures are generated inside the tests, not committed snapshots: a committed index snapshot
  would itself age into another frozen baseline — the exact defect #2709 files.

## Status

OpenSpec change `live-scanner-freshness`; PR from `feat/2709-live-scanner-freshness` (link added
when opened). All tasks ticked against real runs.
