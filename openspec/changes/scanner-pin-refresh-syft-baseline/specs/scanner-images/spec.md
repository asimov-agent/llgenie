## ADDED Requirements

### Requirement: Every scanner image's pinned version is checked against a dated Wolfi baseline

`scripts/security_scan.py` MUST carry a `SCANNER_BASELINE` dict naming, per scanner tool, the Wolfi
release that was current when the pin was last refreshed (dated in the file's comment), and
`make check-security-scan` MUST fail, naming the scanner, when a recorded pin is older than its
baseline (Wolfi `-rN` release ordering, so a lagging pin is loud rather than stale-in-place).

#### Scenario: a lagging scanner pin fails the gate

- **Given** `containers/scanners/digests.json` recording `grype` at a version older than
  `SCANNER_BASELINE["grype"]`
- **When** `make check-security-scan` runs
- **Then** it exits non-zero and names the lagging pin

- **Test:** `tests/test_security_scan.py::test_check_fails_when_a_scanner_version_lags_the_declared_baseline`

### Requirement: The SBOM tool baked into the grype image is recorded and freshness-checked

The grype image bakes `syft` (its SBOM generation step) at an explicit `ARG SYFT_VERSION`.
`containers/scanners/digests.json` MUST therefore record `syft_version` inside the `grype` host
entry (written by `scripts/scanner_image.py` from the Dockerfile's ARG), and `make
check-security-scan` MUST fail when the entry is absent or lags `SCANNER_BASELINE["syft"]` — the
baked tool is as freshness-gated as the scanner it sits inside.

#### Scenario: a lagging baked syft fails the gate

- **Given** a `digests.json` whose `grype` entry carries a `syft_version` older than
  `SCANNER_BASELINE["syft"]`
- **When** `make check-security-scan` runs
- **Then** it exits non-zero and names the lagging `syft` version

- **Test:** `tests/test_security_scan.py::test_check_fails_when_the_baked_sbom_tool_lags_its_baseline`

#### Scenario: a missing baked-syft record is loud

- **Given** a `digests.json` whose `grype` entry has no `syft_version`
- **When** `make check-security-scan` runs
- **Then** it exits non-zero naming `grype` and the absent `syft_version`

- **Test:** `tests/test_security_scan.py::test_check_fails_when_the_sbom_tool_has_no_freshness_record`

### Requirement: A baseline refresh bumps the pin and the image together

When a Wolfi release newer than a baseline lands, the fix is one commit that bumps the Dockerfile
`ARG <TOOL>_VERSION`, the baseline entry, and the image (rebuilt + republished + re-pinned via
`make scanner-digests`), so `digests.json` can never record a version older than the baseline it is
checked against.

#### Scenario: the refreshed pins match the refreshed baselines

- **Given** this change's Dockerfile (`grype 0.121.3-r2`, `syft 1.57.1-r2`) and its baselines
- **When** `make check-security-scan` runs against the committed `digests.json`
- **Then** it exits 0 and no pin lags its baseline

- **Test:** `tests/test_scanner_images.py::test_the_real_digests_record_pins_every_published_scanner_image`
  plus `make check-security-scan`
