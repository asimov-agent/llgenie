# scanner-images delta: Syft gets its own pinned scanner image (issue #746)

## ADDED Requirements

### Requirement: Syft has its own immutable scanner image

`containers/scanners/syft/Dockerfile` MUST exist and follow the same contract as the other
scanner images: a Wolfi base pinned by `@sha256:<64 hex>`, an exact `ARG SYFT_VERSION=<apk build>`
pin (no range, no `latest`), a non-root `USER`, `ENTRYPOINT ["syft"]`, and `CMD ["version"]`.
`syft` MUST join `SCANNERS` in `scripts/scanner_image.py` (`arg: SYFT_VERSION`, `cmd: version`)
and `RELEASE_BASELINE`, so `make scanner-digests` writes its tag/version/ref, `make
check-scanner-images` requires its digest base and exact pin, `make test-scanner-image
SCANNER=syft` runs the binary and asserts the pinned version, and the security-images ensure/publish
legs treat it like the other scanners.

#### Scenario: the syft Dockerfile is contract-checked

- **Given** `containers/scanners/syft/Dockerfile` with a floating base or a missing exact pin
- **When** `make check-scanner-images` runs
- **Then** it exits non-zero naming `syft`

- **Test:** `tests/test_scanner_images.py` (syft Dockerfile digest-pinned with an exact
  `SYFT_VERSION`; a floating syft base fails the check)

#### Scenario: a grype edit never moves the syft tag

- **Given** the four content-hash tags recorded in `containers/scanners/digests.json`
- **When** the grype Dockerfile bytes change (a grype pin bump)
- **Then** only the grype content hash changes; the syft tag is byte-identical, because syft's
  version no longer lives in the grype image

- **Test:** `tests/test_scanner_images.py` (roster isolation: editing one Dockerfile changes
  only its own content hash)

### Requirement: The SBOM step runs Syft's own image with no entrypoint override

`scripts/security_scan.py::sbom` MUST run `image_ref("syft")` — the immutable ref from
`digests.json` — passing the SBOM flags directly to the syft image's own ENTRYPOINT. The
published-image scan (`scan_published_image`) MUST write the image SBOM the same way. No
security-scan path may reach Syft through `--entrypoint syft` on another tool's image.

#### Scenario: sbom names the syft image, not the grype image

- **When** the recorded `_run` argv for `sbom()` is inspected
- **Then** it names `<registry>/llgenie/syft:<content hash>` and carries no `--entrypoint` token

- **Test:** `tests/test_security_scan.py` (the recorded argv names the syft ref; the old
  `--entrypoint syft` assertion is rewritten)

#### Scenario: the SBOM the CVE matcher consumes is unchanged in shape

- **When** `make sbom` runs and then `make security-scan TOOL=grype` matches
- **Then** Grype reads the CycloneDX document Syft wrote at `security-reports/sbom.cdx.json`

### Requirement: Every tool in ALL_TOOLS carries a full digest entry

`make check-security-scan` MUST require, for EVERY tool in `ALL_TOOLS` (including `syft`), a
`digests.json` entry carrying `version`, `tag`, `ref`, and a valid `image_digest`
(`sha256:<64 hex>`). The "the SBOM tool rides the grype image" carve-out is deleted; a scan can
prove which Syft image it ran exactly like it proves which Grype image it ran.

#### Scenario: a missing syft digest entry fails the gate

- **Given** a `digests.json` with no `syft` entry
- **When** `make check-security-scan` runs
- **Then** it exits non-zero naming `syft`

- **Test:** `tests/test_security_scan.py` (the carve-out test is rewritten, not deleted)

## MODIFIED Requirements

### Requirement: The live Wolfi freshness comparison reads every pin from the digest roster

`_pinned_scanner_versions` MUST read each compared package's pin from `digests.json` — including
`syft`, whose pin now lives in its own Dockerfile and entry rather than in the grype Dockerfile's
`ARG SYFT_VERSION`. The live comparison (`make scanner-freshness`, issue #2709) therefore measures
the version the SBOM step actually runs.

#### Scenario: syft's live pin comes from its own entry

- **Given** `digests.json` recording `syft` at the newest published Wolfi build
- **When** `make scanner-freshness` runs against the live index
- **Then** syft is compared from its digest entry and passes without a lag finding

## REMOVED Requirements

### Requirement: The SBOM tool baked into the grype image is recorded and freshness-checked

**Reason**: superseded by this change — Syft is no longer a baked tool. `BAKED_TOOLS`,
`baked_version()`, and the `grype.syft_version` record are deleted; the same freshness floor now
applies through syft's own `RELEASE_BASELINE`/`SCANNER_BASELINE` entries and its digest roster
entry (which the ADDED digest-roster requirement above already enforces for `syft`).
