# Proposal: move the test-suite Makefile domain into mk/tests.mk

## Why

Issue #800 split the top `Makefile` into per-domain `mk/*.mk` includes, and the residual
issues name the domains that still sit in the top file. The test-suite cluster — 18
targets (`test-env` … `download-test-model`, issue #2677) — is the second most-churned
domain: every CI-shape change (a new suite leg) edits the same 977-line file every other
domain edits. #2674 (merged guard lane) gives the split its enforcement; this change
lands the test domain into that guarded shape.

## What Changes

- `mk/tests.mk` is created and appended to the top `Makefile`'s include block (after
  `include mk/bots.mk`), following the proven #2456–#2461 playbook.
- 18 targets move **byte-identically** (target lines, prerequisites, guard comments,
  recipes, `##` help lines): `test-env` `test-clean` `test-unit-network` `test-unit`
  `test-hub-live` `test-strata-live` `agents-read-venv` (+ its stamp rule and the
  `PY312`/`AGENTS_READ_VENV`/`HERMES_AGENT_PIN`/`AGENTS_READ_STAMP` definitions it
  parses with) `test-agents-read` `test-agent-skills-live` `test-board-ownership-host`
  `test-recall-step` `test-top-tier` `test-top-tier-ci` `test-top-tier-serve`
  `test-top-tier-serve-ci` `test-top-tier-cli-ci` `test` `download-test-model`.
- Pure move: no recipe logic, no renames, `.PHONY` entries stay in the top file
  (bots.mk precedent). The `ci-*` job targets stay in `mk/ci.mk`; the image targets
  (`test-image*`, `test-variant-image`) stay for #2678 (images domain); the native-engine
  targets and `NATIVE_HOST`/`NATIVE_GUARD` stay (not in #2677's 18).
- `docs/ARCHITECTURE.md` `mk/` row names `tests.mk` citing this issue; CHANGES.md row
  via `docs/changes.d/` fragment.

## Impact

- `Makefile`: 977 → 837 lines; declared targets 76 → 58 (−18, zero added).
- `mk/tests.mk`: new, 130 lines, 18 targets.
- `make -qp` target inventory identical before/after (the only new entry is the include
  file's own record); `make help` output byte-identical (help is a static echo target).
- Affected specs: `makefile-split` (residual domain lands). Gate coverage unchanged:
  `check_wiring` and `unit_tests.py` are already include-aware and resolve the moved
  targets through the new file.
