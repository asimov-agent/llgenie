# Proposal: scanner pin refresh + syft freshness record

## Why

Two findings from the security-lane audit of #2661 (measured at main `6a56fc94f0034c134db23f9ce4dc62011d1d2699`, re-measured 2026-11-15 against `packages.wolfi.dev/os/x86_64/APKINDEX.tar.gz`):

1. **grype lags Wolfi (issue #2707).** `containers/scanners/grype/Dockerfile` pins
   `GRYPE_VERSION=0.121.2-r1`; Wolfi's x86_64 index now tops out at `0.121.3-r2`. The
   vulnerability matcher the admission gate trusts runs an old build.
2. **syft has no freshness record (issue #2708).** The SBOM generator rides the grype image
   (`ARG SYFT_VERSION=1.57.0-r1`, called via `--entrypoint syft`) and appears in neither
   `SCANNER_BASELINE` nor `containers/scanners/digests.json`. Wolfi publishes `1.57.1-r2`.
   A lagging cataloger narrows SBOM coverage invisibly: components the newer cataloger would
   find never enter the SBOM, so grype never matches them.

Both live in the same image, so both fixes share one image rebuild and one digest re-pin.

## What Changes

- `containers/scanners/grype/Dockerfile`: `GRYPE_VERSION` → `0.121.3-r2`,
  `SYFT_VERSION` → `1.57.1-r2` (the newest published Wolfi builds at bump time).
- `scripts/security_scan.py`: `SCANNER_BASELINE` gains `grype: "0.121.3-r2"` (bumped) and a
  **`syft` entry** (`"1.57.1-r2"`); the freshness loop compares the grype entry's new
  `syft_version` field against `SCANNER_BASELINE["syft"]` — a lagging SBOM tool reds
  `make check-security-scan`.
- `scripts/scanner_image.py`: `RELEASE_BASELINE["grype"]` bumped to match; `write()` records
  `syft_version` (parsed from the grype Dockerfile's `ARG SYFT_VERSION`) into the grype entry of
  `containers/scanners/digests.json`.
- `containers/scanners/digests.json`: rewritten by `make scanner-digests`; the grype tag is the
  content hash of the bumped Dockerfile, and `make pin-scanner-image-digests SCANNER=grype`
  records the published image's manifest digest.
- The bumped grype image is published to GHCR (`ghcr.io/asimov-agent/llgenie/grype:<content-hash>`,
  `linux/amd64,linux/arm64`) through the sanctioned publish path; the package already exists.
- Tests in `tests/test_security_scan.py`: a regression test that `check_security_scan` fails when
  the recorded `syft_version` lags `SCANNER_BASELINE["syft"]`, and passes at parity.

## Not covered

- Shipping syft as its own pinned scanner image — issue #746 (in flight), unchanged here.
- Vulnerability-scanning the built engine/agent images — issue #2706 (separate lane).
- The live Wolfi comparison gate — issue #2709 (separate change, `make scanner-freshness`); this
  change keeps the static baseline honest, that gate catches drift between baselines and Wolfi.
