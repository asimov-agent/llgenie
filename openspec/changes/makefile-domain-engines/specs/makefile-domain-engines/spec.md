# Engine-domain Makefile split

## ADDED Requirements

### Requirement: the engine targets live behind `include mk/engines.mk` with identical recipes

The top `Makefile` keeps the shared environment, `.PHONY`, `version`/`help`,
`.DEFAULT_GOAL` and `include mk/gates.mk` plus `include mk/engines.mk`; the
engine-domain targets (`build-server`, `build-variant`, `skills-validate`, every
`engine-*`, `build-engine*`, `test-engine*`, `test-native-engine*`, `test-built-engine`,
`test-published-engine`, `push-engine`, `run-engine`, `stop-engine`, `ci-engine*`,
`ci-engines`, `ci-wait-engine-images`, `generate-*engine-params`, `engine-bump*`,
`list-engine-images`, `engine-build-matrix`, the `check-engine-*` family, the
`engine-skill-*` / `spawn-engine-skill-issues` / `render-engine-skill-gap` family,
`engine-params-review*`, `engine-pins*`, `engine-capabilit*`, `engine-hardware`,
`engine-plan`, `engine-check`, `engine-install`, `engine-detect`, `engine-smoke`,
`test-engine-host`, `test-engine-stage`, the registry/quant/trend/strata model-data
family `sync-registry`, `check-registry*`, `sync-quant-catalog`, `check-quant-catalog`,
`render-trend-list-matrix`, `check-trend-list-matrix`, `check-vram-scope-view`,
`render-vram-scope-view`, `sync-strata-models`, `check-strata-models`, `check-model-links`,
`model-links-report`, `registry-change-report`, `sync-change-issue`, `registry-review*`,
`registry-sync-review`, `_registry-sync-review`, `_engine-params-review`, the
`install-prism-*` / `install-upstream-*` / `serve-variant` family `build-variant`,
`test-serve-variant`, `stop-serve-variant`, and the internal seams
`test-engine-install`, `generate-build-engine-params`) live in `mk/engines.mk`,
byte-for-byte identical to the pre-split file. A change to the engine surface touches
one small file.

#### Scenario: the target surface is unchanged after the split

Given the current tree on the split branch with `mk/engines.mk` present and included,
when `make -qp` and `make help` are run,
then the target list is identical to the pre-split tree (`make -qp` diff empty) and
`make help` is byte-identical.

### Requirement: the moved targets stay visible to every Makefile-text reader

Every Makefile-text reader resolves `include mk/*.mk`: the readers merged with the gates split
(`check_wiring._makefile_list`, `check_docs` / `architecture_bot._makefile_text`,
`check_dispatch_forms.makefile_targets`, `issue_bot_gates._makefile_text`, conftest
`makefiles_text`) already do, and the unit-suite roster loader `scripts/unit_tests.py` gains the
same resolver (`_makefiles` → `_make_recipes`) so its roster claims stay checked against moved
recipes. No gate goes blind after a domain move.

#### Scenario: a moved engine target stays wired and documented

Given an engine-domain target (e.g. `test-engine-image`, `engine-bump-daily`,
`push-engine`, `sync-quant-catalog`) moved behind `include mk/engines.mk`,
when `make check-wiring` and `make check-docs` run against the split tree,
then both pass with byte-identical output to the pre-split tree, and
`make check-dispatch-forms` / `make check-workflows` / lint stay green.

#### Scenario: the unit-suite roster check sees recipes behind the include

Given the roster in `tests/fixtures/unit-suite.json` names targets that now live in
`mk/engines.mk` (e.g. `test-native-engine`, `test-published-engine`),
when `scripts/unit_tests.py` builds its recipe map,
then every roster `target` claim resolves (zero `[unit-suite]` errors) and
`make test-unit` starts pytest instead of refusing.
