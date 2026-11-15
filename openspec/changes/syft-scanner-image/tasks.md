# Tasks: syft-scanner-image (issue #746)

## 1. Roster and Dockerfile

- [x] 1.1 `containers/scanners/syft/Dockerfile`: Wolfi base pinned by digest (same base as the other three), `ARG SYFT_VERSION=1.57.1-r2` (Wolfi current release, measured 2026-11-15 from the x86_64 APKINDEX), `USER 65532:65532`, `ENTRYPOINT ["syft"]`, `CMD ["version"]`.
- [x] 1.2 `scripts/scanner_image.py`: `SCANNERS["syft"] = {"arg": "SYFT_VERSION", "cmd": "version"}` + `RELEASE_BASELINE["syft"] = "1.57.1-r2"` (baseline comment names the measurement date).

## 2. The scan uses it directly

- [x] 2.1 `scripts/security_scan.py`: `sbom()` runs `image_ref("syft")` with no `entrypoint` override; delete the `SBOM_TOOL` carve-out comments; `check()` requires a digest entry for every tool in `ALL_TOOLS`; `ensure_image_for` resolves syft like `TOOLS`.
- [x] 2.2 `.github/workflows/security-images.yml`: dispatch `scanner` choice list gains `syft`.

## 3. Publish + pin the tag

- [x] 3.1 `make scanner-digests` writes the syft entry (version/tag/ref/dockerfile).
- [ ] 3.2 Publish the content-hash tag multi-arch (`make publish-scanner-images SCANNER=syft`) and record it with `make pin-scanner-image-digests SCANNER=syft`; `make check-scanner-images` green with four scanners.

## 4. Tests

- [ ] 4.1 `tests/test_scanner_images.py`: four roster ids; syft Dockerfile digest-pinned + exact pin; a grype-only edit leaves the syft tag unchanged (issue AC 4).
- [ ] 4.2 `tests/test_security_scan.py`: carve-out test REWRITTEN — `check()` fails without a syft entry; `sbom()` argv names `llgenie/syft:<hash>` with no `--entrypoint`.
- [ ] 4.3 `make test-scanner-image SCANNER=syft` green; `make sbom` + `make security-scan TOOL=grype` green against the published image; `make security-scan TOOL=syft` writes `security-reports/sbom.cdx.json`.

## 5. Docs + gates

- [x] 5.1 `docs/SCANNERS.md` roster table + one-image paragraph; `docs/SCANS.md` SBOM wording; `docs/changes.d` fragment; `agent-wiki` entry naming issue #746.
- [ ] 5.2 `make openspec-validate NAME=syft-scanner-image` passes; `make check-docs`, `make check-wiring`, `make lane-preflight`, `make test-unit` all green.
