# auto-merge-skip-stacked-base

## ADDED Requirements

### Requirement: A PR with a non-`main` base is never armed or merged by the merger

The auto-merge decision SHALL refuse a pull request whose `baseRefName` is not `main`, and SHALL name that
base as the reason, so a stacked PR can never be auto-armed or auto-merged by the merger.

WHEN `decide()` reads a PR whose `baseRefName != "main"` with an otherwise clean, green, open state
THEN it SHALL return a deferral reason naming the non-`main` base, and `make auto-merge` SHALL NOT call
`gh pr merge` on it.

#### Scenario: a stacked PR is deferred with its base named

Given a green, CLEAN, open PR whose `baseRefName` is `feat/another-pr`
When  the `decide()` verdict is read
Then  it is a reason that names `feat/another-pr` and `main`, and `make auto-merge` never merges it.

- **Test:** `tests/test_auto_merge.py::test_a_non_main_base_pr_is_never_armed_or_merged`

#### Scenario: a `main`-base PR still merges normally

Given a green, CLEAN, open PR whose `baseRefName` is `main`
When  the `decide()` verdict is read
Then  it returns `None` (eligible), and the existing merge path is unchanged.

- **Test:** `tests/test_auto_merge.py::test_only_a_clean_merge_state_is_merged`

### Requirement: A hand merge into a non-`main` base is reported by a scheduled check

The merge workflow's scheduled sweep SHALL report every PR merged into a non-`main` base, with the PR
author, the head sha and the count of check-runs that ran at that head (expected 0), so a merge into a
stacked base is visible even after it has landed.

WHEN the scheduled recheck runs
THEN it SHALL run a stacked-base report that lists merged PRs whose `baseRefName != "main"` and, for each,
state the author, the head sha and the number of check-runs at that head.

#### Scenario: the detector names an out-of-main merge

Given a merged PR whose `baseRefName` is `feat/another-pr`
When  the stacked-merged report runs
Then  it names the PR with its author, head sha and the number of check-runs at that head.

- **Test:** `tests/test_auto_merge.py::test_stacked_merged_names_out_of_main_merges`

#### Scenario: a clean board reports zero

Given only merged PRs whose `baseRefName` is `main`
When  the stacked-merged report runs
Then  it reports 0 out-of-`main` merges.

- **Test:** `tests/test_auto_merge.py::test_stacked_merged_reports_zero_when_clean`

### Requirement: `docs/BOTS.md` states the arming rule in one line

`docs/BOTS.md` SHALL carry a one-line rule: *arm only on a PR whose base is `main`; a stacked PR arms on
retarget*.

WHEN `docs/BOTS.md` is read
THEN one line states the arm rule with `main` and `retarget`.

#### Scenario: the arming rule names `main` and `retarget`

Given `docs/BOTS.md`
When  the arming rule is read
Then  one line states *arm only on a PR whose base is `main`; a stacked PR arms on retarget*.

- **Test:** `tests/test_auto_merge.py::test_bots_md_states_the_stacked_arming_rule`
