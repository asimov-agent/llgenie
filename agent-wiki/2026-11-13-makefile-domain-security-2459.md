# 2026-11-13 — Makefile split: security domain into mk/security.mk (issue #2459)

Implements issue #2459 (OpenSpec change `makefile-domain-security`), PR for issue #2459, in the
Makefile decomposition family (issue #800): gates split merged under #2457, engines split merged
via PR #2635 (issue #2456), ci split open as PR #2636 (issue #2458); the closed big-bang #2454
stays superseded. Bots (#2460) and install (#2461) remain their own lanes.

Verified against the spec (measured at the lane head against origin/main `61155e9af`):

- `mk/security.mk` (143 lines) carries exactly the 36 security-domain target blocks moved
  byte-identically from the top Makefile (1,539 -> 1,445 lines): the secret-scan family
  (check-secret-output, secret-output-report, _secret-scan, secret-scan, _secret-scan-history,
  secret-scan-history, secret-scan-self-test) and the security/scanner/supply-chain chain
  (sbom .. renovate-report).
- Span rule: each block runs from its target line through the first blank line OR the next
  target header, whichever comes first (tracking `ifeq` depth). `GITLEAKS_IMAGE :=` /
  `GITLEAKS_RUN :=` are variable assignments: the span stops at them, so the pin definition
  stays in the top Makefile and the recipes reference it via `$(GITLEAKS_RUN)` unchanged.
- Ownership seam (decided in the proposal): `ci-scanner-images` belongs to `mk/ci.mk` (ci split
  #2458), NOT `mk/security.mk`; the `engine-pins` prerequisite named by `sbom` /
  `security-scan-all` resolves through `mk/engines.mk`.
- Reader fix (the lane's only blind gate): `scripts/check_gitleaks_pin.py` now walks the
  resolved makefile chain (`_makefile_list`, mirroring `check_wiring._makefile_list`) for both
  the bare-tag scan and the cross-site digest match — otherwise a tag re-added behind the
  include would escape the pin guard; `tests/test_secret_scan.py`'s two Makefile-reading tests
  (target existence, wrapper recipe slice) and `tests/test_secret_output.py`'s wiring test now read
  `tests/conftest.py::makefiles_text()`.
- Parity: `make -qp` target lists identical (458 targets, diff empty); `make help` and
  `make check-wiring` and `make check-docs` byte-identical to the base tree (banner-line
  normalized); `make check-gitleaks-pin` rc=0 on the resolved set; focused battery 205 passed
  (test_secret_scan, test_secret_output, test_security_bot, test_security_bumps,
  test_requirements_pins, test_check_pr_closing, test_ci_hf_live_workflow, test_ci_scope,
  test_ci_verdict, test_wiring);
  `make lint` / `make check-workflows` / `make check-dispatch-forms` / `make openspec-validate`
  rc=0.

Decisions: banners stay in the top Makefile (#2456/#2458 precedent); the pin guard generalizes
rather than special-casing security.mk; `gp.MAKEFILE` constant kept for test compatibility.

Current status: focused gates green; full battery + PR CI pending on the final head.
