# Proposal: scanner-digest-pin

## Why

`containers/scanners/digests.json` pins each scanner image by a content-hash TAG
(`ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`). The tag names one build of one Dockerfile,
but the tag itself is re-pushable, and a re-build of the SAME Dockerfile resolves whatever the
package repository (wolfi APKINDEX) publishes that day — so "the pinned scan" silently changes
contents when a tag is re-pushed with different resolved packages.

Measured 2026-11-13 while implementing #2577: GHCR `semgrep:5954e2aad609` serves
`sha256:180c3f7e…` while the same tag cached on this host is `sha256:7fd77096…`, and the two
images run semgrep `1.165.0` vs `1.121.0`. A scanner that moved mid-sweep changes what "the
pinned rules + pinned image" means, and findings/verdicts stop being comparable across hosts.
Filed as issue #2609.

## What Changes

- `containers/scanners/digests.json` gains an `image_digest` field per scanner: the manifest
  digest of the image CI publishes for that content-hash tag (recorded by a new
  `make pin-scanner-image-digests`).
- `scripts/security_scan.py` verifies, at every scan invocation on the PULL path, that the image
  it is about to run has exactly the recorded manifest digest; a mismatch exits non-zero naming
  BOTH digests. The deferral path (locally built same-Dockerfile image, issue #2518) prints the
  built image digest and states that the registry pin is not registry-checkable.
- Every scan run prints the executed scanner image digest, so a verdict names the image it was
  made against.
- `make check-security-scan` / `scanner_image.py check` require an `image_digest` for every
  scanner entry.

## Out of scope

- Rebuilding or re-publishing any scanner image (the publish lane already exists; this change
  only records and verifies).
