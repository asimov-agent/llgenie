# Syft ships as its own immutable scanner image

Issue: #746 · Branch: feat/746-syft-image

Syft, the SBOM writer, used to ride the Grype image through `--entrypoint syft`: the
SBOM generator's version was an accident of whatever Grype bundled. It now has its own
`containers/scanners/syft/Dockerfile` (Wolfi base pinned by digest, `SYFT_VERSION=1.57.1-r2`),
a roster entry in `scripts/scanner_image.py`, a published content-hash tag, a digest entry in
`containers/scanners/digests.json`, and a dispatch option in `security-images.yml`. The
`security_scan` carve-out that exempted the SBOM tool from the per-image digest rule is gone —
`check()` now demands a digest entry for every image-backed tool, and `make sbom` runs from the
syft image directly. A Grype bump can no longer move the SBOM generator.
