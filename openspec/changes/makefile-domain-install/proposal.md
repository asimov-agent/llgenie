# Change: makefile-domain-install (issue #2461)

## Why

The top Makefile still carries the whole host-install surface inline — `install`,
`venv-install`, `link`, `smoke`, `uninstall`, the `test-install*` family,
`test-uninstalled`, `test-health` / `test-health-host`, the interactive-TensorFold
drills, and `hf-cli-install`. Issue #800's decomposition has been proven
single-domain four times (gates #2457, engines #2456, ci #2458, security #2459, bots
#2460); this change does the same move for the install domain — the big-bang #2454
stays closed and superseded, and this is the last domain of the family.

## What Changes

- New `mk/install.mk` receives the 16 install-domain target blocks BYTE-IDENTICAL from
  the top Makefile (target names, prerequisites, recipes — including the
  `ifeq ($(HOST_OS),Darwin)` guarded recipe bodies of `test-health`, `test-install-host`
  and the interactive drills — and inline comments unchanged). Each block spans from its
  target line through the first blank line OR the next target header OR the next
  top-level variable assignment, whichever comes first (tracking `ifeq` depth): a
  blank-line-only span bleeds through neighbours with no blank line between them.
- Ownership seams with sibling lanes: `install-prism-*` / `install-upstream-*`,
  `test-built-engine`, `test-engine-install` and `test-native-engine*` already live in
  `mk/engines.mk` (moved by #2456, unchanged here); `ci-install*` are ci-domain and live
  in `mk/ci.mk` (PR #2636), NOT here; `hermes-smoke`, `search-smoke` and `_hermes-smoke`
  are bot-domain and live in `mk/bots.mk` (PR #2641), NOT here. The section banners
  (`# ---- full install…`, `# ---- 1./2+3./4 …`) stay in the top Makefile at their
  original positions (the banner-boundary rule established by the engines/ci splits).
- The top Makefile keeps version/help/.PHONY/.DEFAULT_GOAL and the shared environment
  (`all`, `test`, `loop-harness`, `chained` composites included), and adds
  `include mk/install.mk` beside the existing includes.
- All Makefile-text readers already resolve `include mk/*.mk` (check_wiring,
  check_docs / architecture_bot, check_dispatch_forms, issue_bot_gates, unit_tests);
  tests that read Makefile text read the resolved set via
  `tests/conftest.py::makefiles_text` (merged under PR #2635).
- Measured parity at the head: `make -qp` target list diff EMPTY, `make help`
  byte-identical, `make check-wiring` output byte-identical, `make check-docs`
  byte-identical, the hermetic unit battery green.

## Impact

- Spec: `specs/makefile-domain-install/spec.md` (new capability, delta-only).
- Code: `Makefile` (16 target blocks removed, one include line added), new
  `mk/install.mk`, affected `tests/*` readers re-pointed to `conftest.makefiles_text`.
- Docs: `agent-wiki/` entry, `docs/changes.d/` fragment, `CHANGES.md` row.
- Gates: `make -qp` / `make help` / `check-wiring` / `check-docs` parity; hermetic
  `make test-unit`; lint / check-workflows / check-dispatch-forms; openspec-validate.
- This change closes ONLY issue #2461 (the final domain of the family).
