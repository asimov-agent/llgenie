# Task 1: pin the reference

- [x] Replace the bare `ghcr.io/gitleaks/gitleaks:v8.30.1` tag with the digest reference `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f` in `scripts/secret_scan.py:GITLEAKS_IMAGE` (source of truth).

# Task 2: propagate the pin

- [x] Set `Makefile:GITLEAKS_IMAGE` to the same digest reference.
- [x] Set the scanner literal in `scripts/secret_scan_self_test.py` to the same digest reference.

# Task 3: add the guard

- [x] Add `scripts/check_gitleaks_pin.py` (a `check` subcommand) that fails on a bare `:v` tag, on a divergent cross-site digest, or on a non-`@sha256:<64hex>` reference.
- [x] Add `make check-gitleaks-pin` and wire it into `make check-security-scan`.

# Task 4: document and test

- [x] Document `check-gitleaks-pin` in `docs/SCANS.md`.
- [x] Add the agent-wiki record and docs/changes.d fragment.
- [x] Add a hermetic unit test asserting the pinned state and that the guard reds on a divergent digest.

# Task 5: verify

- [x] `make check-gitleaks-pin` exits 0 on the tree; red on a reverted tag and on a divergent digest (reproduced on an isolated copy).
- [x] `make secret-scan-self-test` green at the new pin (the planted credential is still caught).
- [x] `make check-wiring`, `make check-docs`, `make check-security-scan`, `make lint` green.
