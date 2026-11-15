# Scan published images by digest in the security lane (issue #2706)

## Why

The security lane judges only the source tree: `make security-scan-all` runs `trivy fs .`, Syft
over `dir:.` and Grype over that SBOM, `semgrep scan .` (scripts/security_scan.py). No lane ever
hands a BUILT image — the engine images and the agent image published to GHCR — to `trivy image`
or an image SBOM. The runtime package set the product actually ships (base-image OS packages, pip
wheels installed inside engine Dockerfiles) is invisible to the admission gate: a vulnerable wheel
baked into an engine image, or an OS package that goes CVE inside a base layer, ships green.

## What Changes

- `scripts/security_scan.py` gains `scan_image(ref)`: the SAME digest-pinned scanner images run
  `trivy image`, `syft <ref>` (SBOM) and `grype sbom:` against a target image pulled by registry,
  addressed BY DIGEST (`ref@sha256:…` — the target is refused unless it carries a
  `sha256:<64 hex>` digest, issue #2609's rule applied to scan targets). Reports land in
  `security-reports/` as `image-<slug>.trivy.json` / `.cdx.json` / `.grype.json` plus a
  `image-<slug>.meta.json` recording the exact ref scanned.
- `findings()` picks up image reports too, tagging every image finding with the image ref, so
  `make security-verdict` and `make security-issues` see image findings through the SAME policy
  and the SAME issue path as tree findings (one issue per (advisory, package); the image names
  live in the issue body).
- New manifest `containers/scanned-images.json`: the allow-list of published images the lane
  scans. Engine entries name `(engine, variant)` and resolve to the CURRENT pinned tag through
  `scripts/engine_image.py` (never a stale digest literal); static entries name a ref. The digest
  is resolved from the registry at scan time, then the scan runs against `ref@digest`.
- New make targets: `security-scan-images` (the lane step — manifest), `security-scan-image`
  (REF=<ref@digest> — one image), and `security-scan-fixture` (AC proof: a deliberate
  known-vulnerable fixture image scanned into `security-reports-fixture/` and run through the
  verdict report-only — never filed as issues, never gating).
- `.github/workflows/security-scan.yml` runs `make security-scan-images` between the scan step
  and the verdict step; `.github/workflows/engine-build.yml` scans each JUST-PUBLISHED engine
  image by its pushed digest after `make push-engine` (`continue-on-error`: the published
  artifact is measured, never a red after the push already happened).
- `check-security-scan` validates the manifest (shape + owners) so an empty or malformed
  allow-list is a red, not a silent skip.

## Out of scope (separate issues per policy)

- Bumping the scanner package pins themselves (grype/syft lag) is its own issue.
- Where the step physically lives long-term (ci-pipelines lane ownership review) is the
  deactivated-lane re-home issue spun out of the CI-discipline umbrella.
