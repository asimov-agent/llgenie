# Install-domain Makefile split

## ADDED Requirements

### Requirement: the host-install targets live behind `include mk/install.mk` with identical recipes

The top `Makefile` keeps the shared environment, `.PHONY`, `version`/`help`,
`.DEFAULT_GOAL`, the composite targets `all` / `test` / `loop-harness` / `chained`, the
section banners at their original positions, and the existing domain includes, and adds
`include mk/install.mk`; the install-domain targets `install`, `venv-install`, `link`,
`smoke`, `uninstall`, `test-install`, `test-install-host`, `test-install-ci`,
`test-install-trend`, `test-install-published`, `test-uninstalled`, `test-health`,
`test-health-host`, `test-interactive-tensorfold`, `test-interactive-tensorfold-ci` and
`hf-cli-install` live in `mk/install.mk`, each block byte-identical to the pre-split
top Makefile (target name, prerequisites, recipe lines, inline comments).
`install-prism-*` / `install-upstream-*`, `test-built-engine`, `test-engine-install` and
`test-native-engine*` are engine-domain and live in `mk/engines.mk`, not here;
`ci-install*` are ci-domain and live in `mk/ci.mk`, not here; `hermes-smoke`,
`search-smoke` and `_hermes-smoke` are bot-domain and live in `mk/bots.mk`, not here.

#### Scenario: the install callers keep reaching the same targets

Given `pipeline.yml` / `ci.yml` and the host workflow call `make install`,
`make uninstall`, `make test-install-*` and the `test-health` pair as before,
when those jobs run against the split tree,
then each target resolves through the include with the identical recipe and behaves
exactly as on the pre-split tree.

#### Scenario: parity gates pass on the split tree

Given the current tree on the split branch with `mk/install.mk` present and included,
when `make -qp` and `make help` are run,
then the target list is identical to the pre-split tree (`make -qp` diff empty) and
`make help` is byte-identical.

### Requirement: the moved install targets stay visible to every Makefile-text reader

Every Makefile-text reader resolves `include mk/*.mk`: the readers merged with the
gates split (`check_wiring._makefile_list`, `check_docs` / `architecture_bot._makefile_text`,
`check_dispatch_forms.makefile_targets`, `issue_bot_gates._makefile_text`) and the
unit-suite roster loader `scripts/unit_tests.py` (`_makefiles`, merged with the engines
split) all read the resolved makefile set, and tests read Makefile text through
`tests/conftest.py::makefiles_text`. No gate goes blind after the install domain moves.

#### Scenario: a moved install target stays wired and documented

Given an install-domain target (e.g. `install`, `uninstall`, `test-install-ci`,
`test-health-host`) moved behind `include mk/install.mk`,
when `make check-wiring` and `make check-docs` run against the split tree,
then both pass with byte-identical output to the pre-split tree, and
`make check-dispatch-forms` / `make check-workflows` / lint stay green.

#### Scenario: the unit-suite roster check sees install recipes behind the include

Given the roster in `tests/fixtures/unit-suite.json` names targets that now live in
`mk/install.mk`,
when `scripts/unit_tests.py` builds its recipe map,
then every roster `target` claim resolves (zero `[unit-suite]` errors) and
`make test-unit` starts pytest instead of refusing.
