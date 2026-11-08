# ci-verdict-unjudged-red-blocker — tasks

- [x] `scripts/ci_verdict.py::UNJUDGED_RED_CONCLUSIONS` is pinned equal to `BLOCKING_CONCLUSIONS` (= `auto_merge.RED_CONCLUSIONS`), so a `cancelled`/`neutral` unjudged row is again a named blocker
- [x] `scripts/ci_verdict.py::unjudged_reds` exempts a transient per WORKFLOW FILE (`TRANSIENT_FILES = {auto-merge.yml}` + `TRANSIENT_CONCLUSIONS = {cancelled, neutral}`), not per conclusion class — a `cancelled`/`neutral` row from another workflow blocks and is named
- [x] `tests/test_ci_verdict.py::test_the_blocking_conclusions_are_the_merger_s_rule` also asserts `UNJUDGED_RED_CONCLUSIONS == auto_merge.RED_CONCLUSIONS` — the pin that would have caught #2231
- [x] `tests/test_ci_verdict.py::test_a_cancelled_unjudged_row_from_another_workflow_blocks` — a cancelled/neutral unjudged row from a non-`ci-verdict` workflow IS a named blocker (guard-proven: fails on the pre-fix script)
- [x] `tests/test_ci_verdict.py::test_auto_merges_own_cancelled_row_is_a_transient_not_a_blocker` (renamed from `test_a_cancelled_unjudged_row_is_a_transient_not_a_blocker`) — auto-merge's OWN sweep stays a transient by FILE (#2221 preserved)
- [x] sabotage pair: revert the fix (keep the new tests) → `FAILED test_a_cancelled_unjudged_row_from_another_workflow_blocks` + `FAILED test_the_blocking_conclusions_are_the_merger_s_rule`; restore → `54 passed`
- [x] `docs/BOTS.md` unjudged-red paragraph re-states the enforced contract (cancelled/neutral block and are named; only own rows exempt by file)
- [x] full `tests/test_ci_verdict.py` + `tests/test_ci_scope.py` + `tests/test_auto_merge.py` green; `make verdict-roster` and `make check-workflows` green
- [x] change-note trio: `agent-wiki/2026-11-08-ci-verdict-unjudged-red-blocker-2237.md`, `docs/changes.d/2026-11-08-ci-verdict-unjudged-red-blocker-2237.md`, `CHANGES.md` regenerated via `make changes-index`
- [x] `make openspec-validate NAME=ci-verdict-unjudged-red-blocker` exits 0
