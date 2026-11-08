# syntax=docker/dockerfile:1
#
# Grype + Syft — SBOM generation (Syft) and vulnerability matching (Grype) in one image — its own immutable image (issue #714, parent #713).
#
# Why an image and not an install step in the workflow: a scanner installed at scan time is a
# mutable tool on a mutable base, with network access during the scan. This image fixes the base by
# DIGEST and every package by exact version, so the same scan is the same program everywhere.
#
# Kotlin-style rule this file lives by: no floating tag, no version range, no `latest`.
# `make test-scanner-image SCANNER=grype` must print the pinned version.

FROM cgr.dev/chainguard/wolfi-base@sha256:0feab531471d2edfcca55f18883441cb7df598e724fa2dedf9985273f532eed7

# Syft WRITES the CycloneDX SBOM and Grype READS it. They share this image on purpose: a Grype run
# against the SBOM of a different Syft version is a different result, so the pair is pinned and
# shipped together — the scan pipeline never installs either.
ARG SYFT_VERSION=1.57.0-r1
ARG GRYPE_VERSION=0.121.2-r1
RUN apk add --no-cache ca-certificates "syft=${SYFT_VERSION}" "grype=${GRYPE_VERSION}"

USER 65532:65532
WORKDIR /work
# The image is named for Grype (the consumer) but carries both binaries; `syft` and `grype` are
# called explicitly by the scan step, so the entrypoint is only a version probe.
ENTRYPOINT ["grype"]
CMD ["version"]
