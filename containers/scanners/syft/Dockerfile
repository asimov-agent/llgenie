# syntax=docker/dockerfile:1
#
# Syft — the SBOM generator, as its own immutable image (issue #746, parent #713/#715).
#
# Before this file, Syft was reached through the Grype image with `--entrypoint syft`: its version
# was whatever Grype happened to bundle, so a grype bump silently changed the CycloneDX SBOM that
# every Grype finding is matched against, with nothing in this repository pinning or testing it.
# This image is the fix: the same contract as trivy/grype/semgrep — base pinned by DIGEST, package
# pinned to an EXACT version, tag = hash of this file, version asserted by `make test-scanner-image`.
#
# Where the binary comes from: the Wolfi `syft` package (current release 1.57.1-r2, measured from
# the x86_64 APKINDEX on 2026-11-15) on the SAME digest-pinned wolfi-base the other scanners use.
# The issue's fallback (FROM the pinned grype base) is NOT taken: a standalone pinned upstream
# package is feasible, so the split reference is the one shipped.
#
# Kotlin-style rule this file lives by: no floating tag, no version range, no `latest`.
# `make test-scanner-image SCANNER=syft` must print the pinned version.

FROM cgr.dev/chainguard/wolfi-base@sha256:0feab531471d2edfcca55f18883441cb7df598e724fa2dedf9985273f532eed7

ARG SYFT_VERSION=1.57.1-r2
RUN apk add --no-cache ca-certificates "syft=${SYFT_VERSION}"

USER 65532:65532
WORKDIR /work
# Syft is called explicitly as the entrypoint; the scan never overrides it (`--entrypoint` is gone
# from scripts/security_scan.py), and `grype` reads the SBOM this image writes.
ENTRYPOINT ["syft"]
CMD ["version"]
