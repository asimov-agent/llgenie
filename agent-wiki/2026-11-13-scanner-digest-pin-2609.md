# scanner-digest-pin — record and verify the executed scanner image digest

Issues: [#2609](https://github.com/asimov-agent/llgenie/issues/2609) (this change closes it)

## What was changed

Every scanner ref in `containers/scanners/digests.json` was pinned by a mutable content-hash TAG
(`ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`), and nowhere did the repo record the image
DIGEST behind that tag. A tag is re-pushable — GHCR can repoint it at different bytes, and a host can
hold a stale local build under it — so a "pinned" scan meant different images on CI and on a host.
Measured 2026-11-13: GHCR `semgrep:5954e2aad609` resolves to index digest
`sha256:180c3f7e5696cad357c16ab77034e696b1f0482d1de2d1849a6e2f9d75df2d4b`, while the same tag built on
a host on 2026-11-08 was `sha256:7fd77096…` running semgrep 1.121.0 against a recorded `1.165.0-r0`.

1. `containers/scanners/digests.json` now carries an immutable `digest` per scanner ref — the index
   digest of the image CI publishes, measured with `docker buildx imagetools inspect`.
2. `scripts/security_scan.py` resolves the ref's CURRENT index digest before every scan and refuses —
   raising, naming BOTH digests — when it differs from the recorded one. The resolution is the same
   measurement the digest is recorded from, so a scan can attest which image it runs.
3. Every scan run names the digest it executed.
4. `scripts/scanner_image.py::write` (`make scanner-digests`) records the digest beside
   `version`/`tag`/`ref`, and its `check` fails a digests.json whose entry omits or mangles the digest.

`containers/scanners/*/Dockerfile` are unchanged.

## Verified

- `tests/test_security_scan.py`: every scanner records a `sha256:<64 hex>` digest; `check()` reds a
  scanner with no digest; `verify_digest` refuses a mismatch naming both digests (negative control)
  and names the executed digest on a match.
- `tests/test_scanner_images.py`: `write()` records the published digest; `check` reds a digestless
  digests.json.
- `make check-security-scan` and `make check-scanner-images` pass on the real (committed) digests.
- The hermetic unit suite (`make test-unit`) and `make openspec-validate` gate the PR head.

## Status

Change complete; PR opened against upstream `main`. The digests recorded reflect the images currently
published for the pinned refs; a future re-publish (or Dockerfile bump) will surface a digest
mismatch at scan time until `make scanner-digests` re-records the moved image — which is the point.
