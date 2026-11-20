# scanner-image-push-check

## Why

Issue #2960, measured on main 2026-11-19/20: the scheduled `security-images` lane died with
`failed to push ghcr.io/asimov-agent/llgenie/syft:1844da087d23: denied: permission_denied:
read_package` (run 44521814845) because GHCR lets the job's `GITHUB_TOKEN` write only packages the
Actions identity created, and `llgenie/syft` was created by a publish under the owner PAT. The
builds ran first, the refusal came last — and the half-failed publish left the daily
`security-scan` unable to resolve the pinned tag (`the registry cannot answer for
…syft:1844da087d23 … (issue #2609)`, run 44525107255). `agent-image-push-check` (issue #335)
already proved the cure for exactly this failure shape: ask the registry for a push-scoped token
and initiate the cheapest real write BEFORE the expensive build. The scanner lane has no such
proof, so a locked-out package burns multi-arch builds and disturbs a pinned tag's registry state
before saying why it can never succeed.

## What Changes

- `scripts/scanner_image.py`'s `ensure` seam (the `ci-security-images` job surface) runs the ONE
  existing push-check seam (`scripts/ci_images.py pushcheck`, issue #335) for every scanner whose
  content-hash tag is missing, BEFORE `docker buildx build --push` runs. A refusal names the
  registry's own denial, skips the build entirely, and fails the leg non-zero.
- `scripts/package-layers.json` carries the new `scanner_image → ci_images` allowed edge (the
  scanner publish reusing the push-check seam by design, same as `registry_cache_orphans →
  ci_images`).
- `.github/workflows/security-images.yml` hands the `make ci-security-images` step the same
  credential the job logs in with (`GITHUB_TOKEN: secrets.GITHUB_TOKEN`), so the pre-flight proves
  the identity the publish will actually use.
- Operational recovery on the live repo (post-merge, owner-consented): the `llgenie/syft` package
  created under the owner PAT is removed once, the next lane run re-creates it under the Actions
  identity, and the pinned tag/digest is verified against the registry again.

## Impact

- Affected specs: `scanner-image-push-check` (new capability)
- Affected code: `scripts/scanner_image.py`, `scripts/package-layers.json`,
  `.github/workflows/security-images.yml`, `tests/test_scanner_images.py`
- Affected docs: `ARCHITECTURE.md` (security-images lane), `agent-wiki/` entry, `docs/changes.d/`
- Existing gates keep their shape: no new make target, no new CI job; the check lives inside the
  already-wired `ensure` seam.
