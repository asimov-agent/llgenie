# 2026-11-08 — pin the gitleaks admission scanner by digest (issue #2235, PR #2255)

The secret-scan admission gate (`scripts/secret_scan.py`, `Makefile` secret-scan targets) — the
scanner holding "no committed credential VALUE may reach the repo" on every Linux CI build —
addressed gitleaks by a bare upstream tag (`ghcr.io/gitleaks/gitleaks:v8.30.1`) while every other
scanner in the pipeline is content-addressed via `containers/scanners/digests.json`. A tag is a
label anyone with `packages:write` on that package can re-push (the #810 trust-boundary class).

## Change

- Pin gitleaks in all three reference sites to the multi-arch manifest digest of `v8.30.1`
  (measured via the GHCR registry `Docker-Content-Digest` header on 2026-11-08):
  `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`.
  `scripts/secret_scan.py:GITLEAKS_IMAGE` is the single source of truth; `Makefile:GITLEAKS_IMAGE`
  and the self-test literal carry the identical digest.
- Add `scripts/check_gitleaks_pin.py` + `make check-gitleaks-pin`, wired into `check-security-scan`
  (runs in `ci-unit` and the `security-scan.yml` gate job). The guard reds on: a bare `:v` tag in
  any site (mutable-under-re-push), a digest that differs across the three sites (the #1252/#1262
  silently-unsatisfiable-pin class — a pin no reviewed tree state ever carried), or a reference
  that is not `@sha256:<64 hex>`.
- Document `check-gitleaks-pin` in `docs/SCANS.md`; add a hermetic test asserting the pin state and
  that the guard reds on a divergent digest.

## Verified

- `make secret-scan-self-test` GREEN — the pinned digest still catches the planted credential.
- `make check-gitleaks-pin` green on the tree; red (exit 1) on a reverted bare tag and on a
  divergent digest, both reproduced on an isolated copy.
- `make check-wiring`, `make check-docs`, `make check-security-scan`, `make lint` green locally.
- Hermetic test `tests/test_secret_scan.py::test_gitleaks_is_pinned_by_digest_in_every_site_and_the_guard_reds_on_a_width` passes.
