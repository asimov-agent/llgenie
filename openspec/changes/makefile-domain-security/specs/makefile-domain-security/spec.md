# Security-domain Makefile split

## ADDED Requirements

### Requirement: the security targets live behind `include mk/security.mk` with identical recipes

The top `Makefile` keeps the shared environment, `.PHONY`, `version`/`help`, `.DEFAULT_GOAL`
and the existing domain includes and adds `include mk/security.mk`; the security-domain
targets `check-secret-output`, `secret-output-report`, `_secret-scan`, `secret-scan`,
`_secret-scan-history`, `secret-scan-history`, `secret-scan-self-test`, `sbom`,
`security-scan`, `security-scan-all`, `security-verdict`, `check-security-scan`,
`check-gitleaks-pin`, `security-issues-plan`, `security-issues`, `security-issues-reconcile`,
`check-security-issues`, `security-bot-pick`, `security-bot`, `check-security-bot`,
`security-bumps-plan`, `security-bumps`, `check-security-bumps`, `scanner-image`,
`test-scanner-image`, `scanner-digests`, `pin-scanner-image-digests`, `scanner-ref`,
`semgrep-rules-refresh`, `publish-scanner-images`, `check-scanner-images`, `check-actions`,
`actions-report`, `update-actions`, `check-renovate` and `renovate-report` live in
`mk/security.mk`, each block byte-identical to the pre-split top Makefile (target name,
prerequisites, recipe lines, inline comments). Each moved block spans from its target line
through the first blank line OR the next target header, whichever comes first (tracking
`ifeq` depth). `ci-scanner-images` is the CI job surface target for the scanner-images job
and lives in `mk/ci.mk` (ci split #2458), not here; the `engine-pins` prerequisite resolves
through `mk/engines.mk`.

#### Scenario: the CI callers keep reaching the same targets

Given `pipeline.yml` / `ci.yml` call `make security-verdict`, `make check-security-scan`,
`make secret-scan`, `make ci-scanner-images` and the scanner/renovate gates as before,
when those jobs run against the split tree,
then each target resolves through the include (or through `mk/ci.mk` for `ci-scanner-images`)
with the identical recipe and the jobs behave exactly as on the pre-split tree.

#### Scenario: parity gates pass on the split tree

Given the current tree on the split branch with `mk/security.mk` present and included,
when `make -qp` and `make help` are run,
then the target list is identical to the pre-split tree (`make -qp` diff empty) and
`make help` is byte-identical.

### Requirement: the moved security targets stay visible to every Makefile-text reader

Every Makefile-text reader resolves `include mk/*.mk`: the readers merged with the gates split
(`check_wiring._makefile_list`, `check_docs` / `architecture_bot._makefile_text`,
`check_dispatch_forms.makefile_targets`, `issue_bot_gates._makefile_text`) and the unit-suite
roster loader `scripts/unit_tests.py` (`_makefiles`) all read the resolved makefile set, and
tests read Makefile text through `tests/conftest.py::makefiles_text`. No gate or boundary
test goes blind after the security domain moves.

#### Scenario: a moved security target stays wired and documented

Given a security-domain target (e.g. `security-scan-all`, `secret-scan`, `check-renovate`)
moved behind `include mk/security.mk`,
when `make check-wiring` and `make check-docs` run against the split tree,
then both pass with byte-identical output to the pre-split tree, and
`make check-dispatch-forms` / `make check-workflows` / lint stay green.

#### Scenario: the unit-suite roster check sees security recipes behind the include

Given the roster in `tests/fixtures/unit-suite.json` names targets that now live in
`mk/security.mk`,
when `scripts/unit_tests.py` builds its recipe map,
then every roster `target` claim resolves (zero `[unit-suite]` errors) and
`make test-unit` starts pytest instead of refusing.
