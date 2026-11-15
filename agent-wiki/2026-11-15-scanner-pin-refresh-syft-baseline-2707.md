# Scanner pin refresh + baked-syft freshness record (issues #2707, #2708)

PR: branch `feat/2707-scanner-refresh` (opened for #2707 + #2708 in one change:
both land on the same grype image).

## Verified against the spec (`openspec/changes/scanner-pin-refresh-syft-baseline/`)

- Wolfi latest measured from the committed APKINDEX snapshot: grype `0.121.3-r2`,
  syft `1.57.1-r2` (both published 2026-11-14). The old pins
  (`grype 0.121.2-r1`, `syft 1.57.0-r1`) lagged that.
- `SCANNER_BASELINE` now declares `grype 0.121.3-r2` AND `syft 1.57.1-r2`;
  `check-security-scan` reds a lagging `digests.json` pin and a missing or lagging
  `grype.syft_version` record.
- `scripts/scanner_image.py` records the baked tool's version (`BAKED_TOOLS` →
  `grype.syft_version`) from the grype Dockerfile's `ARG SYFT_VERSION`, but only when the
  host is part of the write — a subset write never reads a Dockerfile it was not asked
  about (found by the existing fixture tests during verification).
- Image rebuilt + republished: `ghcr.io/asimov-agent/llgenie/grype:c52ac5da0f5c`
  (linux/amd64 + linux/arm64, publish leg verified with `imagetools inspect`), then
  `make pin-scanner-image-digests SCANNER=grype` recorded
  `sha256:806d7ac23ea8d70c97d011b097e43997a26353930ff7a1e5dce5dc8331a0ad39`.
- `rules_captured_at` deliberately NOT advanced (2026-11-08): the semgrep rules pack did
  not change; `write()` advancing it unconditionally is a separate defect to be filed.

## Key decisions

- #2707 and #2708 ride one PR: the syft freshness record and the grype pin bump are the
  same image rebuild; splitting them would rebuild the same Dockerfile twice.

## Status

- Local: `make check-security-scan` rc=0, `make check-scanner-images` rc=0,
  `pytest tests/test_security_scan.py tests/test_scanner_images.py` 74 passed,
  `make openspec-validate NAME=scanner-pin-refresh-syft-baseline` rc=0.
