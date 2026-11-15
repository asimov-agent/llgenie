# security-image-scan — capability spec

Capability: `security-image-scan`

## Requirement: the daily sweep scans a real published image by digest

WHEN `make security-scan-all` (scripts/security_scan.py `all`) runs,

THEN the tree scanners run in dependency order (Syft SBOM, then Trivy, Grype, Semgrep) AND an IMAGE
scan runs after them, AND the IMAGE scan resolves the pinned Trivy scanner image (or an override)
AND passes it to the same pinned Trivy image as `trivy image <ref>@<manifest-digest>`,
AND writes `security-reports/trivy-image.json` (a parseable JSON report) AND records the exact
digested ref in `security-reports/image-scan-target`.

#### Scenario: the image scan runs last in the full sweep
Given the SBOM and each tree scanner succeed,
When   `make security-scan-all` runs,
Then   `scan()` is invoked for `trivy`, `grype`, `semgrep` and then `image`.

- **Test:** `tests/test_security_scan.py::test_all_scans_includes_the_image_scan`

#### Scenario: a real published image is scanned by digest
Given a pinned trivy scanner image, whose manifest digest `digests.json` records,
When   `scan('image')` runs,
Then   a `trivy image` invocation targets `<registry>/llgenie/trivy:<tag>@sha256:<64hex>`,
And    writes to `security-reports/trivy-image.json`,
And    the exact ref is recorded in `security-reports/image-scan-target`.

- **Test:** `tests/test_security_scan.py::test_the_image_scan_launches_trivy_image_and_records_the_target`,
  `tests/test_security_scan.py::test_default_image_ref_is_the_pinned_trivy_image_by_digest`

## Requirement: an image advisory is a first-class finding through the same policy and issue path

WHEN a `trivy-image.json` report exists,

THEN `findings()` normalises every advisory in it into the shared finding shape,
AND each normalized finding carries a distinct `trivy-image` source AND the `image` ref it came from,
AND `verdict()` applies the SAME `fail_on`/`require_fix` policy to them (a critical/high image
advisory with a fix gates the daily full run; a report-only event records it without gating),
AND `security-issues` labels the finding `component:container` and names the image in the issue
body's `## Technical`.

#### Scenario: a normalised image finding carries the source and the image
Given a `trivy image` report with one CRITICAL that has a fix, and the ref it was scanned at,
When   it is normalised,
Then   it is one finding with source `trivy-image`, the advisory/package/current/fixed/severity of
       the advisory, and the scanned image recorded.

- **Test:** `tests/test_security_scan.py::test_trivy_image_findings_are_normalised`

#### Scenario: the image report flows through the same findings gate
Given a reports dir with `trivy-image.json` and `image-scan-target`,
When   `findings()` runs,
Then   the image advisory is present with source `trivy-image` and the digested ref recorded.

- **Test:** `tests/test_security_scan.py::test_an_image_finding_flows_through_findings`

#### Scenario: a critical image advisory gates the same verdict
Given a trivy-image report with one CRITICAL that has a fix,
When   `verdict('full')` runs,
Then   it exits non-zero (the shipped surface becomes the thing the gate measures),
And    `verdict('pr')` still complies with the report-only policy (records it, exits 0).

- **Test:** `tests/test_security_scan.py::test_a_critical_image_finding_blocks_the_verdict`

#### Scenario: the owning lane sees the image on the issue
Given an image finding against a container package (e.g. `libssl`),
When   it becomes an issue,
Then   it is labelled `component:container` (the pin owner bumps the image, never a Python
       requirements pin) AND the issue body's `## Technical` names the scanned image.

- **Test:** `tests/test_security_issues.py::test_an_image_finding_is_container_and_names_the_image`

## Requirement: CI runs and exposes the image scan

WHEN the security-scan workflow's dispatch is used or the daily schedule runs,

THEN `make security-scan-all` includes the image scan, AND `image` is a selectable dispatch tool
(making it runnable alone), AND the reports it writes are uploaded with the rest of `security-reports/`.

#### Scenario: image is a first-class dispatch tool
Given the security-scan workflow,
When   a manual dispatch selects `image`,
Then   `make security-scan-image` runs (the image scan alone).

- **Test:** `.github/workflows/security-scan.yml` `tools` choice includes `image`; exercised by
  `make check-workflows` and the `test_the_workflow_uses_the_digests_and_a_manual_form` guard in
  `tests/test_security_scan.py`.
