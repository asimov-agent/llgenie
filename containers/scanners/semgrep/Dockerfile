# syntax=docker/dockerfile:1
#
# Semgrep — SAST over the application code — its own immutable image (issue #714, parent #713).
#
# Why an image and not an install step in the workflow: a scanner installed at scan time is a
# mutable tool on a mutable base, with network access during the scan. This image fixes the base by
# DIGEST and every package by exact version, so the same scan is the same program everywhere.
#
# Kotlin-style rule this file lives by: no floating tag, no version range, no `latest`.
# `make test-scanner-image SCANNER=semgrep` must print the pinned version.
#
# The SAST RULE SET is immutability too (issue #1284): the default registry pack (`p/default`) is a
# live alias that resolves at scan time, so the same tree could red/green differently across weeks
# with no tree change. Instead the pack is fetched once, committed to the repository as
# containers/scanners/semgrep/rules/default.yml, BAKED into this image with the COPY below, and its
# sha256 recorded in digests.json (`semgrep.rules_sha`). A scan runs the committed snapshot, never a
# floating registry fetch — byte-identical for the same tree + the pinned pack.

FROM cgr.dev/chainguard/wolfi-base@sha256:0feab531471d2edfcca55f18883441cb7df598e724fa2dedf9985273f532eed7

# Semgrep needs `git` to fetch a rule set pinned by ref, and CA certs for the registry.
ARG SEMGREP_VERSION=1.165.0-r0
RUN apk add --no-cache ca-certificates git "semgrep=${SEMGREP_VERSION}"

# The content-addressed SAST rule pack (issue #1284): same-tree byte-identical scans, no registry
# fetch at scan time. The build context is containers/scanners/semgrep/, so `rules/` is the context.
COPY rules/default.yml /rules/default.yml

USER 65532:65532
WORKDIR /work
ENTRYPOINT ["semgrep"]
CMD ["--version"]
