# Tasks: scanner-pin-refresh-syft-baseline (#2707, #2708)

## 1. Pin refresh
- [x] 1.1 Bump `containers/scanners/grype/Dockerfile`: `GRYPE_VERSION` 0.121.2-r1 → 0.121.3-r2, `SYFT_VERSION` 1.57.0-r1 → 1.57.1-r2 (Wolfi latest measured from the committed APKINDEX)
- [x] 1.2 Bump `SCANNER_BASELINE["grype"]` → 0.121.3-r2 and add `SCANNER_BASELINE["syft"]` = 1.57.1-r2 with the dated refresh comment
- [x] 1.3 Bump `RELEASE_BASELINE["grype"]` → 0.121.3-r2 in `scripts/scanner_image.py`

## 2. SBOM tool freshness record (#2708)
- [x] 2.1 `scripts/scanner_image.py`: `BAKED_TOOLS` + `baked_version()`; `write()` records `syft_version` inside the `grype` entry of `containers/scanners/digests.json`
- [x] 2.2 `scripts/security_scan.py::check` fails when the `grype` entry lacks `syft_version` or it lags `SCANNER_BASELINE["syft"]`

## 3. Tests
- [x] 3.1 `tests/test_security_scan.py::test_check_fails_when_the_baked_sbom_tool_lags_its_baseline`
- [x] 3.2 `tests/test_security_scan.py::test_check_fails_when_the_sbom_tool_has_no_freshness_record`
- [x] 3.3 Existing baseline-lag test now exercises the bumped grype pin (passes with the new baselines)

## 4. Image rebuild + repin
- [x] 4.1 `make scanner-digests` regenerates `digests.json` for the new tag/content-hash (rules_captured_at kept at 2026-11-08: the rules pack did not change)
- [x] 4.2 `make publish-scanner-images SCANNER=grype` published `ghcr.io/asimov-agent/llgenie/grype:c52ac5da0f5c` (multi-arch; PUB_RC=0 verified by `docker buildx imagetools inspect` in the publish leg)

## 5. Verification
- [x] 5.1 `make check-security-scan`, `make check-scanner-images` and the scanner/security test modules pass locally (rc=0)
- [ ] 5.2 `make openspec-validate NAME=scanner-pin-refresh-syft-baseline` exits 0 and `make test-unit` is green with the new tests collected
