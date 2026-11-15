# 2026-11-15 — Published-image scan coverage (issue #2706)

## What was verified against the spec (`openspec/changes/security-image-scan/`)

- **Digest-enforced targets.** `scan_image(ref, slug)` refuses any target without
  `@sha256:<64 hex>`; `resolve_scan_targets()` resolves each allow-list entry to the **index
  digest the registry serves right now** — the allow-list carries no stale digest literals.
  An engine entry resolves through the pinned params (`engine_image.resolve`) to its exact
  per-pin tag (`llama-cpp:7d7f0287-e536208a-cuda`). An entry the registry has no digest for
  fails the lane by name, never a silent skip.
- **Three-stage shape per image.** Trivy `image --scanners vuln` → Syft CycloneDX SBOM →
  Grype `sbom:` on that SBOM, all three from the pinned scanner images, mounting only the
  reports dir (the checkout is not involved — the target is a registry artifact).
- **One findings pipeline.** `findings()` reads `image-*.trivy.json` / `image-*.grype.json`
  through the same normalisers as tree reports; every finding is tagged `image=ref@digest`
  from the `image-<slug>.meta.json` companion. The verdict/policy modes do not distinguish
  an image finding from a tree finding.
- **Issues name the artifact.** `security_issues.py` `Finding.image` → `component:container`
  classification and the exact `ref@digest` line in `## Technical`; marker idempotency
  unchanged.
- **Loud fixture proof.** `make security-scan-fixture` scans the known-vulnerable
  `alpine:3.15.1`, normalized through `findings()`; a fixture producing no reports exits 1
  (broken proof, never clean green). Measured locally 2026-11-15: **130 findings**
  (trivy 27 + grype 103), every one tagged `image=docker.io/library/alpine:3.15.1@sha256:d6d0a0eb4d40…`,
  rc 0 — and the #2609 stale-local-scanner guard fired first, refused the stale local
  `trivy:0abec50ba0db` copy by digest, and only ran after the pinned digest re-pulled
  (`884909103b4b…` executed == pinned).

## Key decisions

- Allow-list `containers/scanned-images.json` is committed tree content (it defines the
  policy surface); scan *reports* stay run output under git-ignored `security-reports*/`.
- The `engine-build.yml` post-publish scan is `continue-on-error: true`: an already-published,
  binary-verified cell is not reddened by a scanner hiccup; the scheduled `security-scan.yml`
  lane re-runs the same scan strictly and files/holds the findings under the policy.
- `check()` validates the allow-list shape (non-empty, valid slugs, engine entries with a
  variant, fixture declared) and that both lanes carry their scan step — the silent-skip
  defect class is gated, not documented away.

## Current status

Branch `feat/2706-image-scan-coverage` (PR to main closes #2706). 79 security-suite tests
green locally (10 new); fixture rc 0 measured; `check-security-scan` rc 0 measured; full gate
list (`make security-scan-images check-security-scan check-wiring check-workflows check-docs
test-unit lane-preflight openspec-validate`) driven green on the branch before the PR.
