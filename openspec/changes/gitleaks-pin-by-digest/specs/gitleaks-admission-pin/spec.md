# gitleaks-admission-pin

## ADDED Requirements

### Requirement: the gitleaks admission image is pinned by digest

The secret-scan admission gate MUST launch gitleaks from a content-pinned image reference,
never from a bare mutable upstream tag. All three reference sites —
`scripts/secret_scan.py:GITLEAKS_IMAGE` (the single source of truth), `Makefile:GITLEAKS_IMAGE`
and the `scripts/secret_scan_self_test.py` scanner literal — MUST carry the identical
`ghcr.io/gitleaks/gitleaks@sha256:<64 hex>` reference equal to the reviewed pin
`@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`.

WHEN the secret-scan gate runs `make secret-scan` / `make secret-scan-self-test`
THEN gitleaks is launched from that digest-pinned reference, so a re-push of any upstream `:v` tag
cannot change what the admission gate runs.

#### Scenario: the scanner is launched from the digest reference

- **Given** `scripts/secret_scan.py`, the `Makefile` and the self-test all name
  `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`
- **And** no site names a bare `:v` tag
- **When** `make secret-scan` (or `make secret-scan-self-test`) runs
- **Then** gitleaks runs from the digest-pinned image
- **Test:** `tests/test_secret_scan.py::test_gitleaks_is_pinned_by_digest_in_every_site_and_the_guard_reds_on_a_width`

### Requirement: a pin-validity guard reds on a mutable tag, divergence or malformed reference

A `make check-gitleaks-pin` guard (run inside `check-security-scan`) MUST exit non-zero when any
reference site addresses gitleaks by a bare `:v` semver tag (mutable under re-push), when the digest
differs between two reference sites (a silently-unsatisfiable pin no reviewed tree state carried,
the #1252/#1262 class), or when a reference is not of the `@sha256:<64 hex>` form.

WHEN the guard examines the three reference sites
THEN it exits 0 when all three carry the reviewed digest and no tag, and exits non-zero on a bare
tag, a divergent digest, or a malformed reference.

#### Scenario: a bare tag reds the guard

- **Given** a tree where the Makefile's `GITLEAKS_IMAGE` is `ghcr.io/gitleaks/gitleaks:v8.30.1`
- **When** `make check-gitleaks-pin` runs
- **Then** it exits non-zero and names the mutable tag
- **Test:** `tests/test_secret_scan.py::test_gitleaks_is_pinned_by_digest_in_every_site_and_the_guard_reds_on_a_width`

#### Scenario: a divergent digest reds the guard

- **Given** a tree where one reference site names a different, still-valid `sha256:` digest than the others
- **When** `make check-gitleaks-pin` runs
- **Then** it exits non-zero and reports the divergent reference as not the reviewed pin
- **Test:** `tests/test_secret_scan.py::test_gitleaks_is_pinned_by_digest_in_every_site_and_the_guard_reds_on_a_width`

#### Scenario: the pinned tree is green

- **Given** all three sites carry the identical reviewed digest and no tag
- **When** `make check-gitleaks-pin` runs
- **Then** it exits 0 with "no bare tag reference"
- **Test:** `tests/test_secret_scan.py::test_gitleaks_is_pinned_by_digest_in_every_site_and_the_guard_reds_on_a_width`

### Requirement: the self-test still catches a planted credential at the new pin

The admission self-test MUST prove the scanner is not a false green with the digest-pinned image:
a planted fake credential MUST be caught and the cleaned tree MUST be green, both at the pinned
reference.

WHEN `make secret-scan-self-test` runs at the pinned digest reference
THEN the planted `ghp_` value is caught (exit 1), never printed unredacted, and the cleaned tree is green (exit 0).

#### Scenario: a planted credential is caught

- **Given** the digest-pinned gitleaks image
- **And** a temporary tree containing a planted fake `ghp_` credential
- **When** the self-test scans that tree
- **Then** the scan exits non-zero and the value is never printed
- **And** after the plant is removed the same tree scans clean (exit 0)
- **Test:** `tests/test_secret_scan_self_test.py` / `make secret-scan-self-test`
