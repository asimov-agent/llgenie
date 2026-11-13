# 2026-11-13 — Makefile split: host-install domain into mk/install.mk (issue #2461)

Implements issue #2461 (OpenSpec change `makefile-domain-install`), PR for issue #2461, the final
domain of the Makefile decomposition family (issue #800): gates split merged under #2457, engines
split merged via PR #2635 (issue #2456), security split merged via PR #2637 (issue #2459), ci split
open as PR #2636 (issue #2458), bots split open as PR #2641 (issue #2460); the closed big-bang
#2454 stays superseded.

Verified against the spec (measured at the rebased lane head against origin/main `908639c1e`, the
post-#2636 tip — the split was re-cut from main's Makefile on rebase, so the `mk/ci.mk` moves of
#2458 and these install moves compose without conflict):

- `mk/install.mk` (107 lines; the 16 target blocks are kept blank-line separated so the text-slicing tests keep their per-recipe boundaries) carries exactly the 16 install-domain target blocks moved
  byte-identically from the top Makefile (1,321 -> 1,218 lines): `install` (goal line with all
  prerequisites unchanged), `venv-install`, `link`, `smoke`, `uninstall`, `test-install`,
  `test-install-host`, `test-install-ci`, `test-install-trend`, `test-install-published`,
  `test-uninstalled`, `test-health` and `test-health-host` (both `ifeq ($(HOST_OS),Darwin)`
  guarded bodies intact), `test-interactive-tensorfold`, `test-interactive-tensorfold-ci`,
  `hf-cli-install`.
- Span rule (same as #2457/#2456/#2458/#2459/#2460): each block runs from its target line through
  the first blank line OR the next target header OR the next top-level variable assignment,
  whichever comes first (tracking `ifeq` depth). Section banners (`# ---- full install…`,
  `# ---- 1. …`, `# ---- 2+3. …`, `# ---- 4. smoke`) stay in the top Makefile at their original
  positions (#2456/#2458 banner-boundary precedent).
- Ownership seams: `install-prism-*` / `install-upstream-*`, `test-built-engine`,
  `test-engine-install` and `test-native-engine*` stay in `mk/engines.mk` (#2456); `ci-install*`
  belong to `mk/ci.mk` (#2458); `hermes-smoke` / `search-smoke` / `_hermes-smoke` belong to
  `mk/bots.mk` (#2460) — the extraction guard asserts none of them bled into mk/install.mk.
- Reader fixes (the lane's blind readers): `tests/test_loop_test_stage.py` (recipes of
  `test-install-host` / `test-install-ci`), `tests/test_provision_agent_profiles.py` (the
  `install:` goal line) and `tests/test_requirements_pins.py` (the `hf-cli-install` recipe) now
  read `tests/conftest.py::makefiles_text()`; the remaining Makefile-text readers
  (`check_wiring`, `unit_tests._makefiles`, `check_docs`/`architecture_bot`,
  `check_dispatch_forms`, `issue_bot_gates`) were already include-resolving.
- Parity: `make -qp` target lists identical (458 targets, diff empty); `make help` and
  `make check-wiring` byte-identical to the base tree; `make check-docs` rc=0 pre and post with
  only its fragment/entry counts advanced 827 -> 828 by this lane's own index row; focused
  battery and full hermetic battery run against this head.

Decisions: banners stay in the top Makefile; existing `include` lines are untouched (the new
include is appended after `include mk/security.mk`) so the family's include-region rebase
conflicts stay trivial; `MAKEFILE = REPO / "Makefile"` constants kept where tests use them for
non-slice purposes.

Current status: parity + gate proofs green at the lane head; full battery and PR CI drive to green.
