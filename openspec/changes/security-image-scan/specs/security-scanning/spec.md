## ADDED Requirements

### Requirement: published images are scanned by digest with the pinned scanners (lane: security-scan.yml, engine-build.yml)

The security lane SHALL scan the built artifacts the product ships, not only the source tree.
`containers/scanned-images.json` is the allow-list of published images; `make
security-scan-images` resolves each entry's CURRENT ref (engine entries resolve their pinned tag
through `scripts/engine_image.py`), resolves the manifest digest the registry serves, and runs the
digest-pinned trivy/syft/grype against `ref@sha256:<64 hex>`. A scan target without a digest SHALL
be refused. The reports are written into `security-reports/` and carry the exact ref scanned.

#### Scenario: a manifest image is scanned by digest

- **WHEN** `make security-scan-images` runs against the committed manifest
- **THEN** each image produces `image-<slug>.trivy.json`, `image-<slug>.cdx.json` and
  `image-<slug>.grype.json` parseable reports plus a meta record naming the `ref@digest` scanned,
  and a target ref lacking `@sha256:<64 hex>` exits non-zero naming the ref

#### Scenario: engine entries never pin stale digests

- **WHEN** an engine pin bumps and the engine image tag changes
- **THEN** the manifest's `(engine, variant)` entry resolves to the new tag through
  `engine_image.tag` and the digest is read from the registry at scan time — no manifest edit is
  needed to keep the scan current

### Requirement: image findings flow through the same verdict and issue path

Image scan findings SHALL be normalized by the same `findings()` readers, carry the image ref, and
be judged by `security-verdict` under the same policy and gated by the same event rules as tree
findings; `make security-issues` files or updates one issue per (advisory, package) with the image
named in the body. A finding in an image never blocks a merge — the lane fires on its own events
only.

#### Scenario: an image vulnerability becomes a tracked finding

- **WHEN** a scanned image report contains a fix-available HIGH/Critical CVE
- **THEN** `findings()` reports it with `source` trivy/grype and the image ref, `blocking()`
  judges it under the same `fail_on`/`require_fix` rules, and `security-issues` carries the image
  name in the issue body (marker idempotency unchanged)

### Requirement: the fixture scan is a loud, report-only proof

`make security-scan-fixture` SHALL scan a deliberate known-vulnerable fixture image by digest
into `security-reports-fixture/`, run the verdict in report-only mode against those reports, and
exit non-zero when the fixture produces NO findings — the fixture proves the image-scan path is
real, never files issues, and never gates a lane.

#### Scenario: fixture findings are measured, not filed

- **WHEN** `make security-scan-fixture` runs against the pinned fixture image
- **THEN** normalized findings are printed with the fixture image ref, no `security-reports/`
  file is touched, and a fixture scan with zero findings exits non-zero (the proof must fail
  loudly if the scanners see nothing)
