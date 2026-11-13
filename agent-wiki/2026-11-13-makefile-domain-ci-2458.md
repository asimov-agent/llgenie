# Splitting the CI domain out of the Makefile into mk/ci.mk (issue #2458)

Part of the Makefile decomposition family (issue #800 → gates split #2457 merged as
`mk/gates.mk`; engine split PR #2635 in review as `mk/engines.mk`; this lane is the ci
domain; security/bots/install domains stay open as #2459–#2461; the big-bang PR #2454
stays closed and superseded).

## What changed

The top `Makefile` (1,539 lines at origin/main `61155e9af`, post-#2456; 1,934 at
`9f893c095` before it) still carried the single-target-per-CI-job surface inline. This lane
moves 20 ci-domain target blocks —
`ci-lint`, `ci-unit`, `ci-agents-read`, `ci-openspec`, `ci-cpu-health`, `ci-top-tier`,
`ci-install`, `ci-install-product`, `ci-install-run`, `ci-install-dry`,
`ci-install-dry-args`, `ci-install-uninstall`, `ci-slow-rows`, `ci-scope`, `ci-verdict`,
`ci-free-disk`, `ci-requeue-cancelled`, `ci-frozen-reaper`, `ci-scanner-images`,
`ci-image-refs` — out of the top file into a new `mk/ci.mk` (154 lines), byte-for-byte.
The 7-line `# ---- ci-<job>: ONE make target per CI pipeline job (issue #117) ----` section
banner STAYS in the top `Makefile` at its original position (the boundary tests slice from
the `uninstall` recipe to that banner; behind the include it would appear before `uninstall`
in the include-resolved text — the engines split #2456 set the same precedent). The top
`Makefile` (now 1,417 lines) keeps the shared environment, `.PHONY`, `version`/`help` and
carries `include mk/gates.mk` + `include mk/ci.mk`. Span rule: target line through the first
blank line OR the next target header (ifeq depth tracked) — adjacent NON-ci blocks
(check-scanner-images, check-actions/…, check-renovate/…, build-engine-%/run-engine-%/list
and its variables) sit between ci targets with no blank line and stay in the top Makefile.

Ownership seam (decided in the OpenSpec change, mirrored into issue #2458): `ci-engine-images`,
`ci-engines` and `ci-wait-engine-images` are engine-domain and land in `mk/engines.mk`
(PR #2635), not in `mk/ci.mk`.

Measured parity against origin/main `61155e9af`:

- `make -qp` target lists identical before/after (458 ↔ 458, `diff` empty in both directions).
- `make help` byte-identical, rc=0.
- `make check-wiring` output byte-identical, rc=0.
- `make check-docs` output byte-identical, rc=0.
- every Makefile-text reader (`check_wiring._makefile_list`, `check_docs` /
  `architecture_bot._makefile_text`, `check_dispatch_forms.makefile_targets`,
  `issue_bot_gates._makefile_text`, `unit_tests._makefiles`, conftest `makefiles_text`)
  resolves `mk/*.mk` includes generically, so `mk/ci.mk` is seen with no resolver change.

## Key decisions

- Byte-identity check: every moved block (20) must appear verbatim in the pre-split
  `git show origin/main:Makefile` — all 20 verified.
- Block-span pitfall (caught by `test_ci_images::test_every_pipeline_job_runs_one_ci_make_target`
  and `test_ci_variant_matrix::test_install_ci_runs_make_install_and_make_uninstall`): a naive
  "target line + consecutive tab-recipe lines" extraction silently DROPS the
  `ifeq ($(HOST_OS),Darwin) … else … endif` guarded recipe bodies of the five `ci-install*`
  stages. Correct span: target line through the first blank line, conditionals included.
- Tests that regex the Makefile text for moved ci targets are repointed from direct
  `Makefile` reads to `tests/conftest.py::makefiles_text`, same fix the engines lane applied
  to its 17 brittle readers.
- The lane rebases onto main after PR #2635 merges, so the shared test-reader patches are
  already in place and only the ci-specific readers need repointing.

## Current status

OpenSpec change `makefile-domain-ci` (proposal + spec delta + tasks) lands first; split +
parity + battery verification drive the PR green; issue #2458 body synced to the 20-target
scope. Issue: #2458 (family #800).
