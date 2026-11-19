# 2026-11-19: ci-scope wildcards the Makefile split (issue #2942, PR #)

## What was verified

- Spec (`openspec/changes/ci-scope-mk-wildcard/specs/ci-scope-classification/spec.md`): the
  Makefile split is a scope wildcard. `scripts/ci_scope.py::WILDCARDS` now carries `mk/**`;
  `classify(["mk/bots.mk"])` → `unmatched == []`, every class selected, CLI rc=0 (9 of 9 jobs).
- The failure that motivated it: PR #2941 (issue #2931), run 44580098715 (2026-11-19) —
  `[ci-scope] FAILED: mk/agents.mk matches no class` (+ `mk/bots.mk`, `mk/engines.mk`) on a
  recipe-only edit of the leg recipes.
- Precedent measured: 35 merged commits touched `mk/**` since 2026-10-01; every one carried an
  incidental wildcard (`Makefile`, `.github/**`) — scope verdicts rode on accident, not intent.

## Key decisions

- `mk/**` joined WILDCARDS, not a new CLASSES entry: `mk/ci.mk` holds the `ci-scope` target
  itself, `mk/tests.mk` the unit stage, `mk/engines.mk` the engine matrix — these files define
  the stages, so a change there can change what any gate proves. A narrower class assignment
  would under-select (an `mk/engines.mk` edit must re-include the engine jobs).
- `tests/test_ci_scope.py`'s enumerated wildcard parametrize gained `mk/bots.mk`, `mk/ci.mk`,
  `mk/engines.mk` (49 tests green). `DOCS_TRIGGER_IGNORE` tests untouched — mk is not a docs glob.

## Current status

Issue #2942 is the root; the branch is `feat/ci-scope-mk-wildcard`. OpenSpec change
`ci-scope-mk-wildcard` validates. PR #2941 must rebase onto the landed classifier so its
scope job reads `mk/**` as a wildcard.
