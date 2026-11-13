# CI-domain Makefile split

## ADDED Requirements

### Requirement: the CI job targets live behind `include mk/ci.mk` with identical recipes

The top `Makefile` keeps the shared environment, `.PHONY`, `version`/`help`,
`.DEFAULT_GOAL` and `include mk/gates.mk` (plus the other domain includes) and adds
`include mk/ci.mk`; the ci-domain targets `ci-lint`, `ci-unit`, `ci-agents-read`,
`ci-openspec`, `ci-cpu-health`, `ci-top-tier`, `ci-install`, `ci-install-product`,
`ci-install-run`, `ci-install-dry`, `ci-install-dry-args`, `ci-install-uninstall`,
`ci-slow-rows`, `ci-scope`, `ci-verdict`, `ci-free-disk`, `ci-requeue-cancelled`,
`ci-frozen-reaper`, `ci-scanner-images` and `ci-image-refs` live in `mk/ci.mk`, each
block byte-identical to the pre-split top Makefile (target name, prerequisites, recipe
lines, inline comments). The `ci-<job>` section banner moves with the cluster it
documents. `ci-engine-images`, `ci-engines` and `ci-wait-engine-images` are
engine-domain and live in `mk/engines.mk`, not here.

#### Scenario: the CI callers keep reaching the same targets

Given `pipeline.yml` / `ci.yml` call `make ci-unit`, `make ci-scope`, `make ci-verdict`
and the `ci-install*` stages as before,
when those jobs run against the split tree,
then each target resolves through the include with the identical recipe and the jobs
behave exactly as on the pre-split tree.

#### Scenario: parity gates pass on the split tree

Given the current tree on the split branch with `mk/ci.mk` present and included,
when `make -qp` and `make help` are run,
then the target list is identical to the pre-split tree (`make -qp` diff empty) and
`make help` is byte-identical.

### Requirement: the moved CI targets stay visible to every Makefile-text reader

Every Makefile-text reader resolves `include mk/*.mk`: the readers merged with the
gates split (`check_wiring._makefile_list`, `check_docs` / `architecture_bot._makefile_text`,
`check_dispatch_forms.makefile_targets`, `issue_bot_gates._makefile_text`) and the
unit-suite roster loader `scripts/unit_tests.py` (`_makefiles`, merged with the engines
split) all read the resolved makefile set, and tests read Makefile text through
`tests/conftest.py::makefiles_text`. No gate goes blind after the ci domain moves.

#### Scenario: a moved CI target stays wired and documented

Given a ci-domain target (e.g. `ci-unit`, `ci-scope`, `ci-verdict`, `ci-install-dry-args`)
moved behind `include mk/ci.mk`,
when `make check-wiring` and `make check-docs` run against the split tree,
then both pass with byte-identical output to the pre-split tree, and
`make check-dispatch-forms` / `make check-workflows` / lint stay green.

#### Scenario: the unit-suite roster check sees CI recipes behind the include

Given the roster in `tests/fixtures/unit-suite.json` names targets that now live in
`mk/ci.mk`,
when `scripts/unit_tests.py` builds its recipe map,
then every roster `target` claim resolves (zero `[unit-suite]` errors) and
`make test-unit` starts pytest instead of refusing.
