# Change: makefile-domain-security (issue #2459)

## Why

The Makefile on `main` (1,539 lines at `61155e9afc2743f38f4183b78e85571e8e5a41eb`) still piles
the security surface (secret-scan family, sbom, scanners, security issues/bot/bumps, scanner
images, action-pin and renovate gates) and its inline shell/python recipes onto every other
domain. The decomposition family (issue #800) is proven twice already — `mk/gates.mk` (#2457)
and `mk/engines.mk` (PR #2635) — and the ci domain split is open as PR #2636 (issue #2458).
This change does the same move for the security domain; the big-bang #2454 stays closed and
superseded.

## What Changes

- New `mk/security.mk` receives the 36 security-domain target blocks BYTE-IDENTICAL from the
  top Makefile (target names, prerequisites, recipes — including `ifeq`-guarded recipe bodies —
  and inline comments unchanged): `check-secret-output`, `secret-output-report`, `_secret-scan`,
  `secret-scan`, `_secret-scan-history`, `secret-scan-history`, `secret-scan-self-test`, `sbom`,
  `security-scan`, `security-scan-all`, `security-verdict`, `check-security-scan`,
  `check-gitleaks-pin`, `security-issues-plan`, `security-issues`, `security-issues-reconcile`,
  `check-security-issues`, `security-bot-pick`, `security-bot`, `check-security-bot`,
  `security-bumps-plan`, `security-bumps`, `check-security-bumps`, `scanner-image`,
  `test-scanner-image`, `scanner-digests`, `pin-scanner-image-digests`, `scanner-ref`,
  `semgrep-rules-refresh`, `publish-scanner-images`, `check-scanner-images`, `check-actions`,
  `actions-report`, `update-actions`, `check-renovate`, `renovate-report`.
  Each block spans from its target line through the first blank line OR the next target header,
  whichever comes first (tracking `ifeq` depth), so neighbours with no blank line between them
  never bleed into the moved span.
- Ownership seams (decided here, mirrored into issue #2459): `ci-scanner-images` is the CI job
  surface target for the scanner-images job and belongs to `mk/ci.mk` (ci split #2458,
  PR #2636), NOT to `mk/security.mk`; the `engine-pins` prerequisite named by `sbom` and
  `security-scan-all` resolves through `mk/engines.mk` (merged under PR #2635). The section
  banner comments stay in the top Makefile at their original positions (engines split #2456 /
  ci split #2458 precedent: boundary tests slice between banners in the include-resolved text).
- The top Makefile keeps version/help/.PHONY/.DEFAULT_GOAL and the shared environment, and adds
  `include mk/security.mk` beside the existing gates/ci/engines includes.
- All Makefile-text readers already resolve `include mk/*.mk` (merged under #2457 and PR #2635);
  tests read Makefile text through `tests/conftest.py::makefiles_text`. Verify no reader or
  boundary test goes blind once the security cluster moves.
- Measured parity at the head: `make -qp` target list diff EMPTY, `make help` byte-identical,
  `make check-wiring` output byte-identical, `make check-docs` output byte-identical.

## Scope boundary

Only `mk/security.mk` + the one include line + docs/record land here. The bots domain stays
issue #2460, the install/docs domain issue #2461. `ci-scanner-images` is NOT moved here (ci.mk).

## Impact

- Affected specs: `makefile-domain-security` (capability delta: the security domain lives behind
  an include, with parity gates).
- Affected code: `Makefile`, `mk/security.mk` (new), tests that slice Makefile text if they
  prove blind, docs trio (`docs/changes.d/`, `agent-wiki/`).
