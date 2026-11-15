# Syft's own scanner image (#746)

Branch `feat/746-syft-image`, OpenSpec change `syft-scanner-image`. Issue #746.

## What was verified

- `containers/scanners/syft/Dockerfile`: Wolfi base pinned by digest, `ARG SYFT_VERSION=1.57.1-r2`
  (measured from the Wolfi x86_64 APKINDEX), `USER 65532:65532`, `ENTRYPOINT ["syft"]`.
- `make scanner-digests` writes the syft entry; `make test-scanner-image SCANNER=syft` built and
  asserted `syft 1.57.1` locally (rc=0).
- `scripts/security_scan.py`: `sbom()` runs from `image_ref("syft")` (no `--entrypoint` override);
  `check()` requires a digest entry for every tool in `ALL_TOOLS` — the "SBOM tool rides the
  grype image" carve-out is removed; `scanner_baseline()` carries `syft 1.57.1-r2`.
- `security-images.yml`: `syft` is a dispatch scanner option.
- Tests: 70 pass; the 4 publish-dependent gates fail with exactly one cause — the syft
  `image_digest` missing from `digests.json` — which `make pin-scanner-image-digests` supplies
  after the image lands on GHCR (issue #2609's rule).

## Current status

Blocked on publishing `ghcr.io/asimov-agent/llgenie/syft:<content-hash>`: a collaborator's token
cannot create a NEW package under the org (`create_package` denied), and only the
`security-images.yml` GITHUB_TOKEN (build job, `packages: write`) may. Next step: a human
dispatch of `security-images.yml` on branch `feat/746-syft-image` with `scanner=syft` (or owner
permissions for host-side publish), then `make pin-scanner-image-digests SCANNER=syft`, tests
green, PR to `asimov-agent/llgenie:main`.
