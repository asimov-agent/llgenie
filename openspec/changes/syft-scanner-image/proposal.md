# Proposal: syft-scanner-image (issue #746)

## Why

The security stack claims one image per scanner but breaks the rule for Syft:
`containers/scanners/digests.json` pins trivy, grype and semgrep, yet
`make security-scan TOOL=syft` / `make sbom` reach Syft through the **Grype**
image with `--entrypoint syft`. Syft's version is whatever the pinned Grype
build happened to bundle, so a grype bump silently changes the CycloneDX SBOM
that every Grype finding is matched against — invisible to `digests.json`,
`make check-scanner-images` and the tests. Syft is the one scan component with
no digest-pinned base, no exact `ARG` pin, no content-hash tag and no version
test. This is the single exception to the #713/#715 rule "one immutable image
per scanner", and it is the exception that feeds every finding.

## What Changes

- **ADDED** `containers/scanners/syft/Dockerfile`: Wolfi base pinned by
  `@sha256:`, `ARG SYFT_VERSION=1.57.1-r2` (the Wolfi current release measured
  from the x86_64 APKINDEX on 2026-11-15), `USER 65532:65532`,
  `ENTRYPOINT ["syft"]`, `CMD ["version"]` — the same contract as trivy.
  The binary comes from the Wolfi `syft` package on the same digest-pinned
  base the other scanners use; no `FROM` of the grype image (issue option 2 —
  the standalone Wolfi package IS feasible, so it is taken).
- **ADDED** `"syft": {"arg": "SYFT_VERSION", "cmd": "version"}` to `SCANNERS`
  in `scripts/scanner_image.py` plus a `RELEASE_BASELINE` entry — the roster is
  the single edit point, so `scanner-digests`, `check-scanner-images`,
  `test-scanner-image` and the security-images publish lane all gain syft with
  no further changes.
- **MODIFIED** `scripts/security_scan.py`: `sbom()` runs `image_ref("syft")`
  with no `--entrypoint` override; the `SBOM_TOOL` "no image of its own"
  carve-out and its comments are deleted; `check()` requires a digest entry
  for every tool in `ALL_TOOLS`; `ensure_image_for` resolves syft like the
  others.
- **ADDED** syft entry to `containers/scanners/digests.json` via
  `make scanner-digests` + publish + `make pin-scanner-image-digests`
  (never hand-edited), so the syft tag ships a published `image_digest`.
- **MODIFIED** `.github/workflows/security-images.yml`: the dispatch `scanner`
  choice list gains `syft` (`SCANNER=all` already covers it).
- **MODIFIED** tests: `tests/test_scanner_images.py` (four roster ids, syft
  Dockerfile pinned, a grype-only edit cannot move the syft tag);
  `tests/test_security_scan.py` (the carve-out test is REWRITTEN to assert
  `check()` fails without a syft entry; `sbom()` argv records
  `<registry>/llgenie/syft:<hash>` and no `--entrypoint`).
- **MODIFIED** docs pair: `docs/SCANNERS.md` roster table + one-image
  paragraph, `docs/SCANS.md` ("written by Syft from the Grype image" → "from
  its pinned Syft image"), `docs/changes.d` fragment, `agent-wiki` entry.

## Out of scope (separate issues already linked)

- The scanner-images build pipeline itself (#744/#745, landed).
- Scanner version-bump cadence (#739 + Renovate `container-base`).

## Impact

- Affected specs: `security-scanner-images` (ADDED requirements: syft ships as
  its own immutable image; the scan reaches Syft only through that image).
- Affected code: `containers/scanners/syft/Dockerfile` (new),
  `scripts/scanner_image.py`, `scripts/security_scan.py`,
  `containers/scanners/digests.json`, `.github/workflows/security-images.yml`,
  `tests/test_scanner_images.py`, `tests/test_security_scan.py`, docs.
