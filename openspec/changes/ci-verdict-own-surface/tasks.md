# ci-verdict-own-surface — tasks

- [x] `scripts/ci_verdict.py` gains `OUR_WORKFLOW_FILE = ci-verdict.yml` and `UNJUDGED_RED_CONCLUSIONS = {failure, timed_out, startup_failure}`; `unjudged_reds` excludes own-surface rows by workflow FILE and blocks only on genuinely-red unjudged conclusions (`BLOCKING_CONCLUSIONS` unchanged)
- [x] `scripts/ci_verdict.py::main` computes the posted title's word from the EFFECTIVE conclusion, so a green-judged head forced red by unjudged blockers posts `ci-verdict: red`, never `ci-verdict: green`
- [x] `scripts/ci_scope.py::check_run_payload` accepts an optional `title` override and titles the row with it
- [x] `tests/test_ci_verdict.py::test_the_verdicts_own_judge_rows_are_not_unjudged_reds` — fails on the pre-fix script (the own `judge` rows were counted), passes on the fix (guard-proven)
- [x] `tests/test_ci_verdict.py::test_a_cancelled_unjudged_row_is_a_transient_not_a_blocker` — auto-merge `merge=cancelled` no longer reds (fails pre-fix)
- [x] `tests/test_ci_verdict.py::test_a_failure_from_an_unjudged_workflow_still_blocks` — negative control: a real unjudged `failure` still names the red (passes pre-fix too, so the exemption is narrow)
- [x] `tests/test_ci_verdict.py::test_a_failure_conclusion_is_never_titled_green` + title assertions in `test_green_ci_beside_an_unjudged_red_is_not_posted_as_success` — a failure conclusion never posts title `ci-verdict: green`
- [x] live reproduction at 07a7db2a / run 42460411318 — `make ci-verdict` exits 0, `conclusion=success` (was `failure`), `unjudged_reds` returns `[]` (was 5 rows)
- [x] `check_runs_of` pagination contract (#2156) untouched: 192/192 unique rows at head 520db900, no truncation raise
- [x] full `tests/test_ci_verdict.py` + `tests/test_ci_scope.py` green (97 passed); `make verdict-roster` and `make check-wiring` green
- [x] change-note trio: `agent-wiki/2026-11-08-ci-verdict-own-surface-2221.md`, `docs/changes.d/2026-11-08-ci-verdict-own-surface-2221.md`, `CHANGES.md` regenerated
- [x] `make openspec-validate NAME=ci-verdict-own-surface` exits 0
