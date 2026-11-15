# Security lane: the scan now measures a built image, not just the tree (issue #2706)

Implements [#2706](https://github.com/asimov-agent/llgenie/issues/2706) (scan-coverage dimension of
the security-lane audit #2661) — a real published image is now handed to the admission gate by
digest, so the runtime package set the product ships is measured where a CVE actually reaches a user.

## The gap

`make security-scan-all` ran `trivy fs .`, `syft dir:.` and `semgrep scan .` — a tree view. The
OS/pip packages baked into a built engine image or the agent image were invisible to the gate, so a
vulnerable wheel or a base-layer CVE rode to a user inside a green pipeline. The only manifests the
fs scan could see were the dev-tree lockfiles `tools/requirements*.txt`.

## The fix

- `scripts/security_scan.py` gains the IMAGE scan: `scan_image()` runs the SAME digest-pinned Trivy
  image with `trivy image` against ONE real published image pulled by its pinned manifest digest,
  writing `security-reports/trivy-image.json`. The exact ref scanned is recorded beside the report
  in `security-reports/image-scan-target`, so every normalised finding names the image that carries
  the advisory. Default target: the pinned Trivy scanner image itself (real, published, already
  digest-pinned in `digests.json`); an owner points it at an engine/agent image with
  `make security-scan-image IMAGE=<ref>` or a `SECURITY_IMAGE` environment override.
- Findings carry a distinct `trivy-image` source; `scripts/security_issues.py` labels them
  `component:container` (the pin owner bumps the image, never a Python requirements pin) and puts
  the scanned image in the issue body's `## Technical`. The SAME `security-verdict` policy gates
  them (critical/high-and-fixable under the daily full run; report-and-file otherwise).
- Wired through the Makefile: `make security-scan-all` ends with the IMAGE scan; a standalone
  `make security-scan-image` (also `make security-scan TOOL=image`) runs it alone; the dispatch form
  of `security-scan.yml` gains `image` as a scanner choice.

## Verification

- `tests/test_security_scan.py` (+6) and `tests/test_security_issues.py` (+1): normalised shape with
  the image recorded; `findings()`/`verdict()` read the IMAGE report through the same gate; a
  CRITICAL image finding with a fix blocks the full verdict and is report-only under `pr`; a
  `component:container` issue body names the image; `all_scans()` includes `image`; the launched
  argv records `trivy image ... --output security-reports/trivy-image.json <ref>@<digest>`. The
  scanners' real runs are exercised by the `security-scan` CI job, as with the rest of the stack.
- `make test-unit` (the two modules): 75 passed. `make check-security-scan`, `make check-wiring`,
  `make check-docs` green.

The default target (the pinned Trivy scanner image) proves the mechanism end-to-end on every daily
run; pointing it at each published engine/agent image is the harness's extension, tracked as the
owners pin those images (out of this change's scope).
