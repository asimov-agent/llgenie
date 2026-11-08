# Pin the gitleaks secret-scan admission scanner by digest

## Why

The secret-scan admission gate — the scanner holding "no committed credential VALUE may reach the
repo" on every Linux CI build (`pipeline.yml` Linux job → `make secret-scan`) — addressed gitleaks
by a bare upstream tag (`ghcr.io/gitleaks/gitleaks:v8.30.1`) while every other scanner in the
pipeline is content-addressed (trivy/grype/semgrep run from `containers/scanners/digests.json`
refs, guarded by `check-scanner-images`). A tag is a label anyone with `packages:write` on that
package can re-push, changing what the admission gate runs between reviews. This is the #810
trust-boundary class on the scanner that is the least-pinned of all.

## What changes

- The gitleaks image is pinned, in all three reference sites, to the multi-arch manifest digest of
  `v8.30.1` (measured via the GHCR registry `Docker-Content-Digest` on 2026-11-08):
  `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`.
  `scripts/secret_scan.py:GITLEAKS_IMAGE` is the single source of truth; the Makefile's
  `GITLEAKS_IMAGE` and the self-test's scanner literal carry the identical digest.
- A new static guard `scripts/check_gitleaks_pin.py` + `make check-gitleaks-pin` is wired into
  `check-security-scan` (which `ci-unit` and the `security-scan.yml` gate job run). The guard fails
  when any site addresses gitleaks by a bare `:v` tag, when the digest diverges across the three
  sites (the #1252/#1262 silently-unsatisfiable-pin class: a pin no reviewed tree state ever
  carried), or when the reference is not `@sha256:<64 hex>`.
- `docs/SCANS.md` documents the guard; a hermetic unit test asserts the tree is in the pinned
  state and that the guard reds on a divergent digest.

## What does not change

No scanner policy, no `fail_on`/severity set, no allowlist, no `push:`/`pull_request:` trigger on
the scan pipeline. `make secret-scan` and `make secret-scan-self-test` behaviour is otherwise
unchanged — only the exact image reference (resolving to the same `v8.30.1` content) differs.

## Acceptance

- [x] The secret-scan admission gate references gitleaks by a content-pinned `@sha256:` digest in every site, never by a bare `:v` tag.
- [x] `make check-gitleaks-pin` fails when the reference reverts to a mutable tag or diverges across sites, and is wired into a gate CI runs (`check-security-scan`).
- [x] `make secret-scan-self-test` stays green at the new pin — the pinned digest still catches the planted credential.
- [x] No policy/severity/button weakened.
