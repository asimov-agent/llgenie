# Proposal: classify the Makefile split in ci-scope (issue #2942)

## Why

`scripts/ci_scope.py::CLASSES` has no glob for `mk/**` and no wildcard covers it. The `mk/*.mk` files define the CI stages themselves (`mk/ci.mk` holds the `ci-scope` target, `mk/tests.mk` the unit stage, `mk/engines.mk` the engine matrix), yet a diff touching only them reddens the scope job: PR #2941 (run 44580098715, 2026-11-19) failed with `[ci-scope] FAILED: mk/agents.mk matches no class` (also `mk/bots.mk`, `mk/engines.mk`). Every merged `mk/**` commit since 2026-10-01 (35 measured) passed only because its diff incidentally carried a wildcard file (`Makefile`, `.github/**`). Scope verdicts therefore depend on incidental files, not on what a change proves — and a recipe-only mk edit (no new target, so no Makefile change) currently cannot merge.

## What Changes

- Add `mk/**` to `scripts/ci_scope.py::WILDCARDS`: the list the gate names for paths that "can change what any gate proves". The Makefile split is exactly that — a change there can change what every job runs — so it selects every class.
- Mirror the new wildcard in `tests/test_ci_scope.py`'s enumerated wildcard-path parametrize (`mk/bots.mk`), the file's own convention for keeping the two in step.

## Impact

- Affected specs: `ci-scope-classification` (ADDED requirement: the Makefile split is a wildcard)
- Affected code: `scripts/ci_scope.py` (one glob + comment), `tests/test_ci_scope.py` (one param + comment)
- No workflow YAML change: `DOCS_TRIGGER_IGNORE == CLASSES["docs"]` is unaffected (mk is not a docs glob); no test pins the WILDCARDS set to an exact list.
