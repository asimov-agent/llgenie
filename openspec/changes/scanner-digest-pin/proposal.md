# scanner-digest-pin — record and verify the executed scanner digest

Issue: [#2609](https://github.com/asimov-agent/llgenie/issues/2609)

## Why

Every scanner ref in `containers/scanners/digests.json` is pinned by a mutable tag —
e.g. `ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609` — and nowhere does the repo record the image
DIGEST behind that tag. A tag is re-pushable: when GHCR re-publishes it, CI verdicts move with it and
no artifact names the digest a verdict was made against. Measured 2026-11-13:

- GHCR `semgrep:5954e2aad609` resolves to index digest
  `sha256:180c3f7e5696cad357c16ab77034e696b1f0482d1de2d1849a6e2f9d75df2d4b` (`docker buildx
  imagetools inspect`);
- the same tag built on this host on 2026-11-08 is `sha256:7fd77096…` and runs semgrep 1.121.0 while
  `digests.json` declares `1.165.0-r0`.

Nothing at scan time checks which image is actually executed, so `security-verdict`'s "no net new
findings over the #2505 baseline", filed/cleared issues and every "reproduced locally" claim depend on
a pinned ref that is not, in fact, one specific image.

## What Changes

1. **`containers/scanners/digests.json`** carries an immutable `digest` per scanner ref — the index
   digest of the image CI publishes, filled from the registry.
2. **`scripts/security_scan.py`** (the ONE scan seam) resolves the image it is about to run and, when
   its digest differs from the recorded one, exits non-zero naming both digests — a mismatch is an
   error, not drift.
3. **Each scan run states the executed digest** in its output, so a verdict names the image it was
   made against.
4. **`scripts/scanner_image.py::write` (`make scanner-digests`)** records the digest for each scanner
   alongside `version`/`tag`/`ref`, so the file regenerates with its immutability proof, not without
   it.

`containers/scanners/*/Dockerfile` are unchanged. Engine images are already outside this: `registry.json`
pins `@sha256` digests.

## Impact

- Affected specs: `scanner-digest-pin` (ADDED requirement)
- Affected code: `containers/scanners/digests.json`, `scripts/security_scan.py`,
  `scripts/scanner_image.py`, `tests/test_security_scan.py`, `tests/test_scanner_images.py`
- Gates unchanged: `make check-security-scan` / `check-scanner-images` still gate `ci-unit`; the scan
  seam (`security_scan.py scan/check`) is where the digest is required and verified.
