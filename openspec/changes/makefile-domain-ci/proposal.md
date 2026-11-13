# Change: makefile-domain-ci (issue #2458)

## Why

The top Makefile still carries the whole CI job surface inline — the one-target-per-CI-job
span (`ci-lint`, `ci-unit`, `ci-agents-read`, `ci-openspec`, `ci-cpu-health`, `ci-top-tier`,
the `ci-install*` stages, `ci-slow-rows`, `ci-scope`, `ci-verdict`, `ci-free-disk`) plus the
CI-facing bot targets `ci-requeue-cancelled`, `ci-frozen-reaper`, `ci-scanner-images` and
`ci-image-refs`. Issue #800's decomposition was proven single-domain by the merged gates
split (#2457 → `mk/gates.mk`) and is being proven a second time by the engines split
(PR #2635 → `mk/engines.mk`); this change does the same move for the ci domain — the
big-bang #2454 stays closed and superseded.

## What Changes

- New `mk/ci.mk` receives the 20 ci-domain target blocks BYTE-IDENTICAL from the top
  Makefile (target names, prerequisites, recipes — including the `ifeq ($(HOST_OS),Darwin)`
  guarded recipe bodies of the five `ci-install*` stages — and inline comments unchanged).
  Each block spans from its target line through the first blank line OR the next target
  header, whichever comes first (tracking `ifeq` depth): spanning only to blank lines bleeds
  through neighbours with no blank line between them and would drag the adjacent NON-ci blocks
  (check-scanner-images, check-actions / actions-report / update-actions, check-renovate /
  renovate-report, the build-engine-% / run-engine-% / list pattern cluster with its
  UNSUPPORTED/PORT/ARCH_ARGS variables) into the ci domain; those stay in the top Makefile.
  The `# ---- ci-<job>: ONE make target per CI pipeline job (issue #117) ----` section banner
  stays in the top Makefile at its original position (the boundary tests slice from the
  uninstall recipe to that banner; moving it behind the include would move it before
  uninstall in the include-resolved text); the engines split (#2456) established the same
  placement.
- Ownership seam with the engines split: `ci-engine-images`, `ci-engines` and
  `ci-wait-engine-images` are engine-domain and land in `mk/engines.mk` (PR #2635), NOT in
  `mk/ci.mk`; the ci split covers the remaining 20 `ci-*` targets.
- The top Makefile keeps version/help/.PHONY/.DEFAULT_GOAL and the shared environment, and
  adds `include mk/ci.mk` beside the existing includes.
- All Makefile-text readers already resolve `include mk/*.mk` (check_wiring `_makefile_list`,
  check_docs / architecture_bot `_makefile_text`, check_dispatch_forms `makefile_targets`,
  issue_bot_gates `_makefile_text`, unit_tests `_makefiles` — the last merged under PR #2635).
  Tests that read Makefile text read the resolved set via `tests/conftest.py::makefiles_text`.
- Measured parity at the head: `make -qp` target list diff EMPTY, `make help`
  byte-identical, `make check-wiring` output byte-identical, `make check-docs`
  output byte-identical.

## Scope boundary

Only `mk/ci.mk` + the one include line + docs/record land here. Remaining domains stay in
the top Makefile, each its own issue in the family: `#2459` security.mk, `#2460` bots.mk,
`#2461` install.mk.

## Impact

- Affected specs: `makefile-layout` (capability delta: the ci domain lives behind an
  include, with parity gates).
- Affected code: `Makefile`, `mk/ci.mk` (new), docs trio (`docs/changes.d/`, `agent-wiki/`).
