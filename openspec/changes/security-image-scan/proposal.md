# security-image-scan — proposal

Issue: [#2706](https://github.com/asimov-agent/llgenie/issues/2706)

## Why

The security lane judges only the source tree: `make security-scan-all` runs `trivy fs .`, `syft
dir:.` and `semgrep scan .` (scripts/security_scan.py). No lane hands a BUILT image — every engine
image and the agent image published to GHCR — to `trivy image` or `grype image:`. The runtime
package set the product actually ships (base-image OS packages, pip wheels baked into engine
Dockerfiles) is invisible to the admission gate, so a CVE in a wheel or a base layer ships green
inside a pipeline that measures only the dev tree's lockfiles (`tools/requirements*.txt`).

## What Changes

`make security-scan-all` ends with an IMAGE scan: the SAME digest-pinned Trivy image runs
`trivy image` against one real published image pulled by its pinned manifest digest, writing
`security-reports/trivy-image.json` and recording the exact scanned ref in
`security-reports/image-scan-target`. An image advisory flows through the same `security-verdict`
policy and `security-issues` path as a tree finding — `findings()` normalises it with a distinct
`trivy-image` source and the image recorded, the issue path labels it `component:container`, and the
issue body's `## Technical` names the image. The default target is the pinned Trivy scanner image
itself (real, published, already digest-pinned); a standalone `make security-scan-image IMAGE=<ref>`
(and `SECURITY_IMAGE`, and the dispatch `image` choice) points it at an engine/agent image.

## Acceptance

The two acceptance criteria on issue #2706: (1) `make security-scan-all` scans at least one real
published image by digest and writes a parseable report into `security-reports/`; (2) a deliberate
known-vulnerable fixture image flows through `security-verdict` and yields a normalised finding
(test-proven, real scanner run).
