# Tasks — grype pin refresh (#3096)

- [x] Bump `containers/scanners/grype/Dockerfile:18` `ARG GRYPE_VERSION` from `0.121.3-r2` to the Wolfi-published `0.122.1-r0`.
- [x] Run `make scanner-digests` so the shared `containers/scanners/digests.json` grype version/tag/ref match the new Dockerfile (no per-scanner file created).
- [x] Publish the new content-hash grype image and run `make pin-scanner-image-digests SCANNER=grype` to record its manifest digest.
- [x] Prove `make scanner-freshness` rc=0, `make check-scanner-images` rc=0, `make check-security-scan` rc=0 and `make test-scanner-image SCANNER=grype` rc=0.
