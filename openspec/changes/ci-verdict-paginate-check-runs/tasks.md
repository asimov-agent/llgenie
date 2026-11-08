# ci-verdict-paginate-check-runs — tasks

- [x] `scripts/ci_verdict.py::check_runs_of` walks pages (page 1 bare, later `&page=N`), dedupes by id, and refuses only a genuine shortfall (`total_count` unmet by the pages read)
- [x] an empty listing (`total_count == 0`) returns `[]`, never a false truncation refusal
- [x] the unreachable-verdict path is unchanged: exit 2 with no check-run (settle-gate and unreadable-artifact tests still hold)
- [x] `tests/test_ci_verdict.py::test_a_multi_page_check_run_listing_is_fully_walked` — FAILS on the pre-fix script with the exact #2156 error, passes on the fix (guard-proven)
- [x] `tests/test_ci_verdict.py::test_a_genuinely_short_check_run_listing_still_raises` — a short multi-page listing is still refused
- [x] `tests/test_ci_verdict.py::test_an_empty_check_run_listing_is_not_truncation` — `total_count == 0` is a clean `[]`
- [x] live reproduction — `make ci-verdict RUN_ID=42452592982 HEAD_SHA=520db900…` reads all 192, `verdict=green`, names 14 unjudged rows, writes `conclusion=neutral` (SUPERSEDED), rc 0
- [x] full `tests/test_ci_verdict.py` green (49 passed); `make check-docs check-workflows check-wiring lint` green at the head
- [x] change-note trio: `agent-wiki/2026-11-08-ci-verdict-paginate-check-runs-2156.md`, `docs/changes.d/` fragment, `CHANGES.md` regenerated
- [x] `make openspec-validate NAME=ci-verdict-paginate-check-runs` exits 0
