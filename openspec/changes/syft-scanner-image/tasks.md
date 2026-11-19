# Tasks: syft-scanner-image (issue #746)

- [x] `containers/scanners/syft/Dockerfile` — Wolfi base pinned by the same digest the grype
      image uses, `ARG SYFT_VERSION=1.57.2-r0` (Wolfi latest measured 2026-11-19), `USER
      65532:65532`, `ENTRYPOINT ["syft"]`, `CMD ["version"]`; comment states the acquisition
      path (Wolfi `syft` apk package, same as the other three).
- [x] `scripts/scanner_image.py` — add `"syft"` to `SCANNERS` (`arg: SYFT_VERSION`,
      `cmd: version`) and `RELEASE_BASELINE` (`1.57.2-r0`); delete `BAKED_TOOLS`,
      `baked_version()` and the `write()` baked-tool loop.
- [x] `scripts/security_scan.py` — `sbom()` and `scan_published_image` run `image_ref("syft")`
      with no `--entrypoint` override; drop `_run`'s `entrypoint` parameter; `check()` requires a
      full digest entry for every tool in `ALL_TOOLS` and the baked-syft freshness block is
      replaced by the roster loop over `ALL_TOOLS`; `_pinned_scanner_versions` reads syft from
      `digests.json`; `ensure_image_for` resolves `ALL_TOOLS` through `ensure_image`;
      `SCANNER_BASELINE["syft"]` bumped to `1.57.2-r0` with a re-measured date; SBOM_TOOL
      comments updated.
- [x] `containers/scanners/digests.json` — `make scanner-digests` writes the syft entry; publish
      the syft tag (linux/amd64 + linux/arm64) and record `image_digest` via
      `make pin-scanner-image-digests SCANNER=syft` (the #2716 publish/pin sequence).
- [x] `tests/test_scanner_images.py` — roster carries four ids; syft Dockerfile digest-pinned
      with exact pin; floating syft base fails the check; a grype edit changes only the grype
      tag (issue #746 AC: grype bump never moves the syft tag).
- [x] `tests/test_security_scan.py` — carve-out test rewritten: `check()` fails when digests.json
      has no syft entry; baked-syft record tests retargeted to the roster; `sbom()`'s recorded
      argv names the syft ref with no `--entrypoint`; live-freshness pin source is the entry.
- [x] Real proofs: `make test-scanner-image SCANNER=syft`; `make sbom` produces
      `security-reports/sbom.cdx.json` run by the syft image; `make security-scan TOOL=grype`
      matches that SBOM; `make security-scan-all` green; `make check-scanner-images` and
      `make check-security-scan` green with four scanners.
- [x] Docs: `docs/SCANNERS.md` (roster + "one image per scanner"), `docs/SCANS.md` SBOM wording,
      `docs/changes.d/` fragment, `agent-wiki/2026-11-19-syft-scanner-image.md` (names #746).
- [x] Gates: `make openspec-validate NAME=syft-scanner-image`, full `make test-unit`,
      `make lane-preflight` green at the pushed head.
