# syntax=docker/dockerfile:1
#
# Syft — the SBOM generator its own immutable image (issue #746, parent #713).
#
# Until this file existed, Syft was reached through the Grype image with
# `--entrypoint syft`, so its version was "whatever the pinned Grype build bundled": a grype
# bump silently changed the tool that WRITES the CycloneDX SBOM every Grype finding is matched
# against. Splitting it out is the point of this file — the SBOM generator is now pinned,
# content-hashed, and version-tested on its own, and the grype image's bundled Syft is unused.
#
# Binary acquisition: the Wolfi `syft` apk package — the same acquisition path trivy, grype and
# semgrep take. No upstream release artifact download, no build stage: the exact package version
# is the pin.
#
# Kotlin-style rule this file lives by: no floating tag, no version range, no `latest`.
# `make test-scanner-image SCANNER=syft` must print the pinned version.

FROM cgr.dev/chainguard/wolfi-base@sha256:0feab531471d2edfcca55f18883441cb7df598e724fa2dedf9985273f532eed7

# The newest published Wolfi build of syft, measured 2026-11-19 from
# packages.wolfi.dev/os/x86_64/APKINDEX.tar.gz (issue #2709 freshness floor: bump with the
# baseline in scripts/security_scan.py via `make scanner-digests` + PR).
ARG SYFT_VERSION=1.57.2-r0
RUN apk add --no-cache ca-certificates "syft=${SYFT_VERSION}"

USER 65532:65532
WORKDIR /work
# Syft's own ENTRYPOINT: `security_scan.sbom()` runs this image directly with SBOM flags, no
# `--entrypoint` override on another tool's image (issue #746). The version probe keeps the
# `make test-scanner-image SCANNER=syft` assertion honest.
ENTRYPOINT ["syft"]
CMD ["version"]
