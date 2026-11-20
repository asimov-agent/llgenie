# 2026-11-20 — scanner publish is push-checked before it builds (issue #2960)

Refs: issue #2960 (root cause of the daily `security-images` red lane), PR #TBD (OpenSpec change `scanner-image-push-check`).

## What was verified against the spec
- **Measured failure**: `security-verdict`/publish step of `security-images.yml` refused at
  push — `llgenie/syft@1844da087d23` lives under the org but was created by the owner PAT,
  so the lane's `GITHUB_TOKEN` got `DENIED permission_denied: read_package` (runs 2026-11-16…19,
  4 consecutive reds). The buildx build burned first; the deny came last.
- **Fix shape** (the #335 pattern, same seam): `scripts/scanner_image.py ensure` now calls
  `ci_images.pushcheck(sid)` — token exchange scoped `repository:<pkg>:push` + empty-blob
  upload — for each scanner it would publish, BEFORE `docker buildx build --push`. On refusal:
  name the scanner, quote the registry's own error body, print `the build is skipped`, fail rc=1.
- **Credential wiring**: the `make ci-security-images` step in `security-images.yml` is handed
  `GHCR_TOKEN: ${{ secrets.GITHUB_TOKEN }}` so the pre-flight proves the exact identity the
  login step publishes with (job keeps `packages: write`).
- **Wiring**: new cross-group edge `scanner_image -> ci_images` in `scripts/package-layers.json`
  (the proc-gate rule for cross-group imports).
- **Tests** (`tests/test_scanner_images.py`): the two pre-existing in-process `ensure` tests were
  updated to assert pushcheck PRECEDES the `--push` call; a new test proves refusal skips the
  build entirely; two subprocess tests against a stub GHCR prove the real HTTP order
  (token→upload→then build, via a probe file the fake runtime reads) and the loud refusal;
  one test pins the workflow wiring. Verified: `pytest tests/test_scanner_images.py
  tests/test_package_layers.py tests/test_ci_images.py` 87 passed; `make lint`,
  `make check-wiring`, `make check-workflows`, `make openspec-validate` all rc=0.

## Key decisions
- Reuse the ONE push-check seam (`ci_images.pushcheck`) rather than a scanner-local variant —
  one code path, per the no-second-implementation rule.
- Refusal FAILS the leg loudly rather than skipping the scanner quietly: a denied package is a
  real publishing defect (loudness rule, #312).

## Current status
Branch `feat/scanner-image-push-check-2960`; unit battery + PR pending this session. Live effect
lands only after merge: the next `security-images` run push-checks `llgenie/syft` with
`GITHUB_TOKEN` — if the owner grants Actions write (or republishes the package under Actions),
the lane goes green on its own schedule; if not, it now fails fast at the check, naming the
denial before any build burns.
