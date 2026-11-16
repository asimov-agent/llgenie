# Spec: the pairwise dedupe bots scan every open issue, paged to exhaustion

## ADDED Requirements

### Requirement: `bot_claims.paginate_open_issues` returns every open issue, paged to exhaustion

`bot_claims.paginate_open_issues(gh_call, repo, per_page=100)` walks
`repos/{owner}/{repo}/issues?state=open&per_page=100&page=N` through the caller's `gh_call` seam,
collecting pages until a SHORT page (fewer than `per_page`) — so the whole open board is read with
no fixed window. Pull requests (which the `issues` endpoint returns alongside issues) are filtered
out, and each issue is normalised so `createdAt` is present (mapping API `created_at`), matching the
shape `gh issue list --json` produced.

#### Scenario: a board larger than one window is read to exhaustion, not truncated

Given an open board of MORE than `per_page` issues (e.g. 205), newest-first
And a page walk via `gh_call` that returns `per_page` issues per page until a short final page
When `paginate_open_issues` runs
Then every open issue is returned (the full 205, not the first 200)
And a pull request entry in the API payload is excluded

- **Test:** `tests/test_issue_dedup.py::test_a_pair_straddling_the_old_200_boundary_is_still_found`
- **Test:** `tests/test_issue_cleaner.py::test_a_close_behind_open_list_position_200_is_still_seen`

### Requirement: `issue_dedup.candidates` scans the whole open board

`issue_dedup.candidates` gathers its issues through `bot_claims.paginate_open_issues` instead of the
old single `gh issue list --limit 200` page, so a duplicate pair whose OLDER member sits past open-list
position 200 is still a candidate and can still be picked as the canonical issue. A claimed
(agent-labelled) issue and a bot-generated tracker issue remain excluded exactly as before.

#### Scenario: a duplicate pair straddling the old 200-boundary is still detected

Given 205 open issues, newest-first, with a similar pair whose older member is the OLDEST (position 201+)
When the dedup sweep picks the best pair
Then it finds the straddling pair with the older issue as canonical
And the pair is written to `dedup-in.md` for the agent leg

- **Test:** `tests/test_issue_dedup.py::test_a_pair_straddling_the_old_200_boundary_is_still_found`

### Requirement: `issue_cleaner.open_issues` scans the whole open board

`issue_cleaner.open_issues` gathers open issues through `bot_claims.paginate_open_issues`, so an issue
an implemented merged PR closed, that sits beyond open-list position 200, is still seen and the
stale-open close fires instead of being silently skipped.

#### Scenario: a merged PR close behind the old 200-boundary is still acted on

Given more than 200 open issues, newest-first, whose implemented issue is the OLDEST (position 201+)
And a merged PR whose merge commit carries `Issue: #<that number>` with no body closing reference
When the cleaner scans the open board
Then it reports and closes that issue (the merged-PR stale-open) instead of reporting nothing

- **Test:** `tests/test_issue_cleaner.py::test_a_close_behind_open_list_position_200_is_still_seen`
