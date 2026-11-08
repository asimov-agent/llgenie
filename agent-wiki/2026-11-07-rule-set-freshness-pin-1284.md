# Security lane: the semgrep rule set is pinned and the scanner engines are floored (issue #1284)

Implements [#1284](https://github.com/asimov-agent/llgenie/issues/1284) (one finding from this
lane's own continuous-improvement audit, rule-set-freshness dimension) — the SAST rules a scan runs
are now as immutable as the binaries, and the engine versions cannot silently straggle.

## The gap

Semgrep was invoked with `--config p/default`, a registry alias that re-resolves at scan time, so
the same tree re-scanned a week apart could give different results with no tree change. The scanner
binaries were digest-pinned but the rules they ran (and the engine versions) were not.

## The fix

- **Pinned rule set** — the semgrep `p/default` pack is fetched once and committed as
  `containers/scanners/semgrep/rules/default.yml`, baked into the image by the Dockerfile `COPY`,
  and its sha256 is recorded as `semgrep.rules_sha` in `containers/scanners/digests.json`. The
  semgrep scan leg runs `--config <committed pack>` (never `p/default`, never `auto`), and strips
  the wall-clock `time`/`profiling_results` blocks so two scans of the same tree + pack are
  byte-identical.
- **Declared current-release baseline** — `scripts/scanner_image.py::RELEASE_BASELINE` and
  `scripts/security_scan.py::SCANNER_BASELINE` name the current wolfi apk release per scanner
  (semgrep 1.165.0-r0, trivy 0.70.0-r5, grype 0.121.2-r1, syft 1.57.0-r1 — the GitHub 1.183/0.76
  releases are not apk-installable, so the honest "current" is the apk baseline, per the issue's own
  language). `make check-scanner-images` / `make check-security-scan` fail when a pinned engine is
  older than the baseline or when digests.json omits the rule-pack sha; the grype/syft pair was
  bumped `0.121.0-r0/1.55.0-r1` → `0.121.2-r1/1.57.0-r1`.
- **Renovate** — a regex manager now advances the scanner `*_VERSION` ARGs so they move with
  `make scanner-digests` + a PR.

## Verification

- `make scanner-digests`: wrote digests.json with `semgrep.rules_sha` and an updated grype/semgrep
  content-hash tag; `make check-scanner-images` and `make check-security-scan` both exit 0.
- `tests/test_security_scan.py`: committed-pack scan argv, byte-identical output after timing-strip,
  gate reds on missing `rules_sha` and on a lagging engine baseline — all pass in llgenie/test.
