# tasks — makefile-domain-security

## 1. The split

- [x] 1.1 `mk/security.mk` carries ONLY the security-domain targets (36 blocks, names + recipes byte-identical from the pre-split Makefile, `ifeq`-guarded recipe bodies included; banner comments stay in the top Makefile; span rule: blank line OR next target header) — AC1
- [x] 1.2 the top `Makefile` keeps version/help/.PHONY/.DEFAULT_GOAL/environment and adds `include mk/security.mk` beside the existing includes — AC2

## 2. The readers

- [x] 2.1 every Makefile-text reader resolves `include mk/*.mk` (merged under #2457 + PR #2635); `scripts/check_gitleaks_pin.py` walks the resolved chain (`_makefile_list`); `tests/test_secret_scan.py`'s two Makefile-reading tests and `tests/test_secret_output.py`'s wiring test read `conftest.makefiles_text()` — AC2/AC3

## 3. Parity measurement

- [x] 3.1 `make -qp` target list diff EMPTY before/after — AC1
- [x] 3.2 `make help` byte-identical before/after — AC1
- [x] 3.3 `make check-wiring` output byte-identical pre/post split, rc=0 — AC3
- [x] 3.4 `make check-docs` output byte-identical pre/post split, rc=0 — AC3
- [x] 3.5 affected unit modules green in the test container on the split tree (205 passed: test_secret_scan, test_security_bot, test_security_bumps, test_requirements_pins, test_check_pr_closing, test_ci_hf_live_workflow, test_ci_scope, test_ci_verdict, test_wiring) — AC3
- [x] 3.6 `make lint` / `make check-workflows` / `make check-dispatch-forms` green on the split tree — AC3

## 4. Documentation

- [x] 4.1 `agent-wiki/` entry referencing issue #2459 (family #800 → #2456/#2457/#2458/#2459; superseded #2454)
- [x] 4.2 `docs/changes.d/` fragment + `make changes-index` row

## 5. CI

- [x] 5.1 PR CI (ci.yml jobs that call these targets) green on the PR head; this PR closes only issue #2459 — AC3
