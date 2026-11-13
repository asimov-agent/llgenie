# Splitting the engine domain out of the Makefile into mk/engines.mk (issue #2456)

Part of the Makefile decomposition family (issue #800 → gates split #2457 merged as
`mk/gates.mk`; this lane is the engine domain; ci/security/bots/install domains stay open as
#2458–#2461; the big-bang PR #2454 stays closed and superseded).

## What changed

The top `Makefile` (1,919 lines at branch point) carried the whole engine / inference-image /
registry-sync surface inline. This lane moves 96 engine-domain target blocks — `build-server`,
`build-variant`, `skills-validate`, the `engine-*` / `build-engine*` / `test-engine*` /
`test-native-engine*` families, `push-engine` / `run-engine` / `stop-engine`, `ci-engine*`,
`engine-bump*`, the `check-engine-*` gates, the engine-skill family, `engine-params-review*`,
`engine-pins*`, the registry / quant-catalog / trend-list / strata model-data family, the
prism/upstream install + serve-variant family and the internal seams — out of the top file into
a new `mk/engines.mk`, byte-for-byte. The top `Makefile` (now 1,524 lines) keeps the shared
environment, `.PHONY`, `version`/`help` and carries `include mk/gates.mk` + `include mk/engines.mk`.

Measured parity at the branch head:

- `make -qp` target list identical before/after (455 targets, `diff` empty).
- `make help` byte-identical (the `help` target is a fixed echo block; the split cannot move a line).
- `make check-wiring` output byte-identical before/after, rc=0.
- `make check-docs` output byte-identical before/after, rc=0.
- `make check-dispatch-forms`, `make check-workflows`, `make lint` rc=0 on the split tree.
- affected unit modules green in the `llgenie/test` container on the split tree.

## Key decisions

- Target set = the engine-domain family the closed reference split (`wt/t_c053503d`, PR #2454)
  put in `mk/engines.mk`, plus the engine targets main gained after that branch point
  (`ci-engines`, `ci-wait-engine-images`, `test-engine-bump-live`, `test-native-engine*`);
  `sync-agent-profile` is NOT engine-domain and stays with the bots family (#2460's scope).
- Makefile-text readers must all resolve `include mk/*.mk`. Four already did (merged under #2457);
  the unit-suite roster loader `scripts/unit_tests.py` did not — it refused to start pytest once
  engine recipes moved (`tests/fixtures/unit-suite.json` "names `make test-native-engine`, which
  is not a make target"). This lane adds `unit_tests._makefiles`, the same include-order resolver
  `check_wiring._makefile_list` uses; `_make_recipes` now reads the resolved makefile set.
- The split itself is a pure move: zero recipe edits, zero new targets, `make <target>` names unchanged
  for every CI caller.

## Current status

Issue #2456 → branch `feat/makefile-split-engines` → PR (this change) → CI green → closes #2456.
