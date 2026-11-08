# ci verdict paginate check runs

## ADDED Requirements

### Requirement: The verdict reads EVERY check-run on a head, across pages

`scripts/ci_verdict.py::check_runs_of` must return the head's complete set of check-runs even when it
exceeds one API page of 100. The GitHub `list check runs for a commit` endpoint paginates by `page`
for a fixed `per_page=100`; a busy `main` head reports more (measured: 192 at head `520db900`). The
fetch walks pages (page 1 in the bare form the existing stubs match, later pages with `&page=N`),
dedupes by id, and refuses only a GENUINE shortfall — the pages read still fall short of
`total_count`, or a page ends before it and the next adds nothing. An empty listing (`total_count == 0`)
is a clean `[]`, never a false refusal. A well-formed multi-page listing is NOT truncation.

#### Scenario: a head with more than 100 check-runs is read completely

Given a head whose check-runs listing reports `total_count: 192` and is split across two pages
(`per_page=100`: page 1 returns 100 rows, page 2 returns 92),
When `check_runs_of("o/r", head_sha)` walks the listing,
Then it returns all 192 rows (deduplicated), with no truncation refusal.
- **Test:** `tests/test_ci_verdict.py::test_a_multi_page_check_run_listing_is_fully_walked`

#### Scenario: a listing whose pages still fall short is refused

Given a head reporting `total_count: 192` whose pages together deliver only 100 rows,
When `check_runs_of("o/r", head_sha)` walks the listing,
Then it raises `RuntimeError` naming `truncated listing` — a short listing is never a verdict.
- **Test:** `tests/test_ci_verdict.py::test_a_genuinely_short_check_run_listing_still_raises`

#### Scenario: an empty head is a clean empty list

Given a head whose listing reports `total_count: 0` and delivers no rows,
When `check_runs_of("o/r", head_sha)` walks the listing,
Then it returns `[]` and walks no page past page 1 — the empty case is not a shortfall.
- **Test:** `tests/test_ci_verdict.py::test_an_empty_check_run_listing_is_not_truncation`

#### Scenario: the real #2156 specimen reaches a verdict

Given a finished `CI` run at head `520db900` (`run 42452592982`, branch `main`) whose head carries 192
check-runs,
When `make ci-verdict RUN_ID=42452592982 HEAD_SHA=520db900… CHECK_RUN_OUT=<file>` runs at the fixed
head,
Then it reads all 192, holds the run to its decision (`verdict=green success=10 failure=0`), names the
unjudged blocking rows (#2116), and writes a check-run payload (here `conclusion=neutral`, SUPERSEDED
by a later `main` run) — rc 0, not the old exit-2 truncation error.
- **Verification:** the branch-head reproduction recorded in `agent-wiki/2026-11-08-ci-verdict-paginate-check-runs-2156.md`
