# 2026-11-19 — Syft has its own scanner image (issue #746)

Implements issue #746 (OpenSpec change `syft-scanner-image`): the SBOM tool stops
riding the Grype image via `--entrypoint syft` and becomes the fourth entry of the
scanner image roster.

## What was verified against the spec

- **Dockerfile contract** — `containers/scanners/syft/Dockerfile`: Wolfi base pinned
  by the same `@sha256:` digest the grype image uses, exact `ARG SYFT_VERSION=1.57.2-r0`
  (Wolfi latest measured 2026-11-19 from `packages.wolfi.dev/os/x86_64/APKINDEX.tar.gz`),
  `USER 65532:65532`, `ENTRYPOINT ["syft"]`, `CMD ["version"]`. Acquisition path: the
  Wolfi `syft` apk package — same path as the other three, no fork of the grype base.
- **Roster** — `SCANNERS["syft"] = {arg: SYFT_VERSION, cmd: version}`; digest/tag/ref/
  build/test/ensure/check/pin all became four-scanner operations with no other code edits
  (the roster is the single edit point, as the issue predicted).
- **Baked-tool mechanism deleted** — `BAKED_TOOLS`, `baked_version()` and the `write()`
  loop that recorded `grype.syft_version` are gone from `scanner_image.py`;
  `security_scan.py`'s `_run(entrypoint=…)` parameter, the `check()` carve-out ("requiring
  an entry for it would demand an image that does not exist") and the grype-Dockerfile ARG
  read are gone. Freshness for every tool comes from its own `digests.json` entry.
- **Live proofs (2026-11-19, host nerdctl/docker + GHCR)**:
  - `make test-scanner-image SCANNER=syft` green;
  - publish + `make pin-scanner-image-digests SCANNER=syft` → GHCR
    `llgenie/syft:1844da087d23`, multi-arch manifest `sha256:f59cf75c939fd1d9…`, pinned
    into `digests.json` with `version: 1.57.2-r0`;
  - `make sbom` ran `ghcr.io/asimov-agent/llgenie/syft:1844da087d23` (digest-verified,
    no `--entrypoint` in the recorded argv) and produced `security-reports/sbom.cdx.json`;
  - `make security-scan TOOL=grype` matched that SBOM (rc=0);
  - `make security-scan-all` green with all four tools from their own image digests;
  - `make scanner-freshness` passes with syft compared from its own entry;
  - `make check-scanner-images` and `make check-security-scan` green with four scanners.
- **Tag isolation asserted (AC 4)** — `test_a_grype_edit_never_moves_the_syft_tag` moves a
  grype pin in a fixture tree and proves the syft content hash (the tag) does not move.

## Key decisions

- **Wolfi apk package, not an upstream release artifact.** The other three scanners are
  Wolfi `apk add` pins; syft follows the same path, so the version pin is comparable to
  `scanner-freshness`'s Wolfi APKINDEX baseline without a download-and-verify step.
- **No `FROM` of the pinned grype base** (the issue's fallback option 2 was not needed —
  the clean Wolfi package path is feasible).
- **Publish needed a `gh auth token | docker login ghcr.io` refresh first**: the host's
  stored ghcr login was inferior to the PAT (`create_package` denied) — fixed, not coded around.
- **The security-images job keeps its single publish step** (`make ci-security-images`):
  the version assertion for every scanner, syft included, lives in `make test-scanner-image`
  and the unit gates — the same shape trivy/grype/semgrep have; no new CI step was invented
  for one tool.
- `agents/llgenie-planner/skills/github-workflow-admission` was updated so the archived
  `--entrypoint syft` trick can't be recommended again; `make sync-agent-profile
  PROFILE=llgenie-planner` re-verified byte-for-byte (965 files).

## Current status

Branch `feat/syft-scanner-image`; unit suite green; PR opened with `closes #746`;
all OpenSpec tasks ticked.
