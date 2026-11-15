# Tasks: live-scanner-freshness (#2709)

## 1. The live comparison seam

- [x] 1.1 `scripts/security_scan.py`: APKINDEX parse (`_wolfi_stanzas`; local snapshot via
      `WOLFI_APKINDEX`, network fetch otherwise), newest-build resolution per package
      (`_version_sort_key` reuse), and `scanner_freshness()` comparing the `digests.json` pins
      (trivy/semgrep/grype) + the syft ARG pin parsed from `containers/scanners/grype/Dockerfile`.
- [x] 1.2 Failure shape: non-zero exit, one report line per stale/absent pin naming package,
      pinned version, live newest; zero exit prints the index snapshot source.

## 2. Make wiring

- [x] 2.1 `make scanner-freshness` target in `mk/security.mk`; `make check-security-scan` stays
      offline/hermetic (asserted by a test); the `security-scan.yml` lane runs the step captured
      (`id: freshness`, `continue-on-error`) and raises it only in its LAST step.

## 3. Tests (hermetic, fixture index)

- [x] 3.1 Fixture APKINDEX stanzas generated inside the tests (`tmp_path` snapshots via
      `WOLFI_APKINDEX`): pins-equal-newest, pin lagging beyond grace, lag inside grace, package
      absent. Committed snapshots would themselves age into frozen baselines — the defect #2709 files.
- [x] 3.2 `tests/test_security_scan.py`: 8 new tests — stale pin reds naming the delta; fresh lag
      inside grace passes and is printed; absent package reds; unreadable snapshot refuses; grace
      constant + index URL pinned by test; `check()` stays network-free; lane wiring asserted.
      No network in any test.

## 4. Docs

- [x] 4.1 agent-wiki entry `2026-11-15-live-scanner-freshness-2709.md` + `docs/changes.d/`
      fragment + `docs/SCANS.md` target row naming #2709 and the #2661 audit.

## 5. Verification

- [ ] 5.1 `make openspec-validate NAME=live-scanner-freshness` exits 0 and `make test-unit` is
      green with the new tests collected.
