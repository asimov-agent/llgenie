# scanner-image-push-check

## ADDED Requirements

### Requirement: a scanner publish proves the credential can push BEFORE any build

The `ci-security-images` job surface (`scripts/scanner_image.py ensure`) MUST run the existing
push-check seam (`scripts/ci_images.py pushcheck`, issue #335) for every scanner whose
content-hash tag the registry is missing, BEFORE it issues `docker buildx build --push` for that
scanner. A scanner whose tag is already present keeps its skip — the check runs exactly when a
write is about to happen.

WHEN the security-images lane decides to publish a missing scanner image
THEN the push-check runs first, and a credential that cannot push stops the leg before any build
is issued.

#### Scenario: the push-check precedes the build for a missing tag

- **Given** a registry that answers the scanner tag as absent and a push credential the package
  accepts
- **When** `scanner_image.py ensure` runs for that scanner
- **Then** the registry was asked for a push-scoped token (`GET /token` with
  `scope=repository:llgenie/syft:push`) and the empty blob upload (`POST
  /v2/llgenie/syft/blobs/uploads/`) BEFORE the buildx build command was issued
- **Test:** `tests/test_scanner_images.py::test_a_missing_scanner_is_push-checked_before_it_is_built`

### Requirement: a refused push skips the build and fails with the registry's own words

When the push-check refuses, `ensure` MUST NOT issue the buildx build for that scanner, MUST
print the registry's own refusal (the denial body `ci_images.pushcheck` surfaces), and MUST exit
non-zero naming the scanner — so a locked-out package can never again burn multi-arch builds or
disturb the registry state of a pinned tag.

WHEN the registry denies the empty upload for a scanner package
THEN `ensure` exits non-zero, its output carries the refusal, and the build command for that
scanner was never issued.

#### Scenario: denial before build, never after

- **Given** a registry that grants the token but denies the empty upload (403 with a GHCR-style
  denial body)
- **When** `scanner_image.py ensure` runs for that scanner
- **Then** it exits non-zero, its output names the refusal, and no `buildx build … --push`
  command for that scanner ever reached the container runtime seam
- **Test:** `tests/test_scanner_images.py::test_a_denied_push_skips_the_build_and_names_the_refusal`

### Requirement: the lane hands the publish step the credential it logs in with

The `security-images.yml` build job MUST give the `make ci-security-images` step the same
credential the job logs into GHCR with (`GITHUB_TOKEN: secrets.GITHUB_TOKEN`), so the pre-flight
proves the identity the publish will actually use.

WHEN the security-images build job's steps are read
THEN the step running `make ci-security-images` carries `GITHUB_TOKEN` and the job keeps
`packages: write`.

#### Scenario: the publish step is handed the login credential

- **Given** `.github/workflows/security-images.yml`
- **When** the `build` job's steps are read
- **Then** the `make ci-security-images` step has `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` in
  its `env`
- **Test:** `tests/test_scanner_images.py::test_the_publish_step_is_handed_the_login_credential`
