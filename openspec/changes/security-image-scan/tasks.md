# security-image-scan — Tasks

Issue: [#2706](https://github.com/asimov-agent/llgenie/issues/2706)

- [x] 1. `scripts/security_scan.py`: add the IMAGE scan. `default_image_ref()` resolves the pinned
      Trivy scanner image by its `digests.json` manifest digest (or `SECURITY_IMAGE` overrides it);
      `scan_image()` records the ref in `security-reports/image-scan-target` and runs the same
      pinned Trivy image with `trivy image ... --output security-reports/trivy-image.json`; `scan`
      routes the tool id `image` to it; `all_scans()` runs the IMAGE scan after the tree scanners;
      `findings()` reads `trivy-image.json` and normalises each advisory with source `trivy-image`
      and the scanned image recorded.
- [x] 2. `scripts/security_issues.py`: `component_of` returns `component:container` for the
      `trivy-image` source; the `Finding` carries the `image`; the issue body's `## Technical`
      names the scanned image.
- [x] 3. Makefile: `make security-scan-image` (declared `.PHONY`); `make security-scan-all` now ends
      with the IMAGE scan; `make security-scan TOOL=image` runs it alone.
- [x] 4. `.github/workflows/security-scan.yml`: `image` is a dispatch `tools` choice and is routed to
      `make security-scan-image`.
- [x] 5. Tests: `tests/test_security_scan.py` (normalised shape + image recorded; `findings()` and
      `verdict()` read the IMAGE report through the same gate; a critical image finding blocks the
      full verdict and is report-only under `pr`; `all_scans` includes `image`; the launched argv +
      target sidecar); `tests/test_security_issues.py` (a `component:container` image finding whose
      body names the image). Wired via `make test-unit` discovery.
- [x] 6. Docs + record: `docs/SCANS.md` (the IMAGE scan, its outputs and the targets table);
      `agent-wiki/2026-11-15-security-image-scan-2706.md` + `docs/changes.d/` fragment; `make
      changes-index` regenerates `CHANGES.md`.
- [x] 7. Verification: `make check-security-scan`, `make check-wiring`, `make check-workflows`,
      `make check-docs`, `python3 scripts/lint_linefeeds.py`, and `tests/test_security_scan.py` +
      `tests/test_security_issues.py` (75 passed) all green; `make openspec-validate
      NAME=security-image-scan` valid (run in CI where the container CLI has docker).
