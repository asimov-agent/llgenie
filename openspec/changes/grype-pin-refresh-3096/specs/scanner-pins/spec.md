# Spec: scanner pin freshness

## ADDED Requirements

### Requirement: the grype inventory names one published fresh build

The grype scanner SHALL pin `ARG GRYPE_VERSION` in
`containers/scanners/grype/Dockerfile` to the newest Wolfi-published build adopted by this
change (`0.122.1-r0`), and the shared `containers/scanners/digests.json` SHALL record that same
version, the Dockerfile's content-hash tag/ref, and the manifest digest of the published image
serving that tag. No per-scanner `digests.json` SHALL be created.

#### Scenario: freshness gate measures the bumped pin

- **Given** the committed Dockerfile and the live Wolfi x86_64 APKINDEX,
- **when** `make scanner-freshness` runs,
- **then** it exits 0 with no stale-pin problem, and `make check-scanner-images` accepts all four
  scanner inventory entries including grype's new tag and `image_digest`.

#### Scenario: the recorded image is the built image

- **Given** the bumped Dockerfile,
- **when** `make test-scanner-image SCANNER=grype` builds and probes the image,
- **then** it prints grype `0.122.1`, matching the numeric part of the pinned apk version.
