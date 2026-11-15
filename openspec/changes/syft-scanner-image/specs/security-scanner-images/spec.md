## ADDED Requirements

### Requirement: Syft ships as its own immutable scanner image

The repository SHALL build Syft as its own image from `containers/scanners/syft/Dockerfile` under
the same contract as trivy, grype and semgrep: a base pinned by `FROM image@sha256:<64 hex>`, an
exact `ARG SYFT_VERSION=<version>` pin (no range, no `latest`), a non-root `USER`, and
`ENTRYPOINT ["syft"]`. The roster `SCANNERS` in `scripts/scanner_image.py` SHALL carry a `syft`
entry (`arg: SYFT_VERSION`, `cmd: version`) so `make scanner-digests`, `make check-scanner-images`,
`make test-scanner-image SCANNER=syft` and the security-images publish lane treat it like the other
three, and `containers/scanners/digests.json` SHALL record its version, content-hash tag, ref and
published `image_digest`.

#### Scenario: the gate sees four scanners

- **WHEN** `make check-scanner-images` runs on a tree whose syft Dockerfile floats its base or omits the exact pin
- **THEN** it exits non-zero naming the syft problem, exactly as it does for the other three ids

#### Scenario: the version stays proven

- **WHEN** `make test-scanner-image SCANNER=syft` builds the image and runs its version command
- **THEN** the output contains the numeric part of the pinned `SYFT_VERSION`

### Requirement: the scan reaches Syft only through its pinned image

`scripts/security_scan.py` SHALL resolve `image_ref("syft")` from `digests.json` and `sbom()` SHALL
run that image directly with no `--entrypoint` override. The `SBOM_TOOL` carve-out ("the SBOM tool
rides the grype image") SHALL be gone: `check()` requires a digest entry for every tool in
`ALL_TOOLS`, and `ensure_image_for` resolves syft through `ensure_image` like the CVE scanners.

#### Scenario: sbom names the syft image

- **WHEN** `make sbom` builds its scan command
- **THEN** the argv names `<registry>/llgenie/syft:<content-hash>` and contains no `--entrypoint`
- **AND** the produced CycloneDX SBOM still matches under `make security-scan TOOL=grype`

#### Scenario: a missing syft digest entry fails the check

- **WHEN** `digests.json` lacks the syft entry while the scan check runs
- **THEN** the check exits non-zero naming syft (the carve-out is gone)

### Requirement: a grype change cannot move the Syft pin

The syft image SHALL be independent of the grype image: its Dockerfile SHALL NOT `FROM` the grype
image, and a change to the grype Dockerfile SHALL NOT change the syft content-hash tag, its pinned
version, or the SBOM the scan produces. A test SHALL assert this independence.

#### Scenario: grype-only edit, syft tag unmoved

- **WHEN** the grype Dockerfile is edited (version pin or base) and the tags are recomputed
- **THEN** the syft tag and pinned version are unchanged
