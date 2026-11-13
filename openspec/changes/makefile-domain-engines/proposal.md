# Change: makefile-domain-engines (issue #2456)

## Why

The top Makefile still carries the whole engine-build / install / validate surface
(build-server, build-variant, skills-validate, engine-*, publish/test engine images,
the registry-sync family) inline. Issue #800's decomposition was proven single-domain
by the merged gates split (#2457 → `mk/gates.mk`); this change does the same move for
the engine domain — the big-bang #2454 stays closed and superseded.

## What Changes

- New `mk/engines.mk` receives the 96 engine-domain target blocks BYTE-IDENTICAL from
  the top Makefile (target names, prerequisites, recipes, comments unchanged).
- The top Makefile keeps version/help/.PHONY/.DEFAULT_GOAL and the shared environment,
  and adds `include mk/engines.mk` beside the existing `include mk/gates.mk`.
- Every Makefile-text reader must resolve `include mk/*.mk`. Four already do (check_wiring
  `_makefile_list`, check_docs / architecture_bot `_makefile_text`, check_dispatch_forms
  `makefile_targets`, issue_bot_gates `_makefile_text` — all merged under #2457). The unit-suite
  roster loader `scripts/unit_tests.py` did NOT: it parsed only the top `Makefile` and refused
  to start pytest once engine targets lived in `mk/engines.mk` ("names `make test-native-engine`,
  which is not a make target"). This change adds `unit_tests._makefiles`, the same
  include-order resolver `check_wiring._makefile_list` uses, and `_make_recipes` now reads the
  resolved makefile set.
- Measured parity at the head: `make -qp` target list diff EMPTY (455 targets),
  `make help` byte-identical, `make check-wiring` output byte-identical,
  `make check-docs` output byte-identical.

## Scope boundary

Only `mk/engines.mk` + the one include line + docs/record land here. The remaining
domains stay in the top Makefile and each gets its own issue in the family:
`#2458` ci.mk, `#2459` security.mk, `#2460` bots.mk, `#2461` install.mk.

## Impact

- Affected specs: `makefile-layout` (new capability delta: the engine domain lives
  behind an include, with parity gates).
- Affected code: `Makefile`, `mk/engines.mk` (new), docs trio (`docs/changes.d/`,
  `agent-wiki/`).
- CI callers: unchanged target names, so ci.yml / pipeline.yml need no edit.
