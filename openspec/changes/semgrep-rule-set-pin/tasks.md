# Pin the semgrep rule set and floor the scanner engines

- [x] `scripts/scanner_image.py`: `RELEASE_BASELINE` per scanner + `_older` helper; `write()` records the semgrep rules pack sha; `check()` fails on missing/mismatched `rules_sha` and on a version older than baseline.
- [x] `scripts/security_scan.py`: `SCANNER_BASELINE` + scanner/version helpers; the semgrep scan leg uses the committed pack (`--config <repo>/rules/default.yml`, not `p/default`) and strips wall-clock timings; `check()` fails on missing `rules_sha` or a lagging engine.
- [x] `containers/scanners/semgrep/rules/default.yml` committed pack + `containers/scanners/digests.json` `semgrep.rules_sha`; semgrep Dockerfile `COPY`; grype/syft bump + digests.
- [x] `renovate.json` scanner-version regex manager.
- [x] Tests (test_security_scan.py, and semgrep gate/freshness cases); all green in llgenie/test.
- [x] Docs (SCANNERS.md, SCANS.md) + agent-wiki note + changes.d fragment.
- [ ] Gates: make bot-preflight, check-security-scan, check-scanner-images, check-docs, lint, openspec-validate all pass.
