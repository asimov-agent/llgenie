# registry-change-issue

## ADDED Requirements

### Requirement: the store-review marker is resolved through issue search, never a 100-issue listing

`scripts/registry_change_issue.py::open_issue` MUST find the open issue that already carries a
store's marker via GitHub issue search (`gh api search/issues -f q='repo:"<slug>"
"registry-sync-changes: <utc>" in:body state:open'`), not by scanning the first 100 entries of
a newest-first open listing. Because search scores the marker string against the WHOLE open
board, a marker-bearing issue is the one updated regardless of how many issues sit between it
and the newest — a board that has simply grown past 100 open issues must never cause the same
store to be filed twice.

When the search returns the marker-bearing issue, the hit routes through the existing semantics:
the body is updated over REST PATCH (`#2673` path, proven by an exact read-back) and the issue
is re-labelled `agent:implement` over the REST labels endpoint when the label is missing
(`#724`). Only a search that returns NO marker-bearing issue opens a new issue (#704's create
path).

#### Scenario: a marker issue ranked past the 100-issue window is updated, not re-created

- **Given** an open board of more than 100 issues whose marker-bearing issue carries the store's
  marker and sits LAST — past the 100-issue window a truncated open listing could ever see
- **When** a re-run opens that same store
- **Then** the marker-bearing issue past the window is UPDATED (REST body PATCH, label re-queue
  when missing) and no second issue is created
- **Test:** `tests/test_registry_change_issue.py::test_a_marker_issue_ranked_past_the_open_window_is_still_updated`

#### Scenario: a marker-bearing open issue is still found inside the window

- **Given** an open issue that carries this store's marker and no label (the measured #710/#749
  state)
- **When** the report is opened for that same store
- **Then** it is updated over REST PATCH, never through `gh issue edit` (GraphQL `updateIssue`
  refused by the leg's PAT, #2673), and re-labelled `agent:implement` over the REST labels
  endpoint
- **Test:** `tests/test_registry_change_issue.py::test_a_second_open_for_the_same_store_updates_instead_of_duplicating`

#### Scenario: a store with no open marker issue creates exactly one

- **Given** a store whose marker is in no open issue body
- **When** the report is opened
- **Then** exactly one issue is created, scoped to the same repo, and labelled `agent:implement`
  through the REST labels endpoint
- **Test:** `tests/test_registry_change_issue.py::test_a_store_with_no_open_issue_creates_exactly_one`

#### Scenario: a failed body write or label write still reports and survives

- **Given** gh accepting a REST PATCH but never storing the new body (the #819 silent drop), or
  a credential that refuses the write (the #775 403 class)
- **When** the update runs
- **Then** the step fails loudly naming the issue for a silent drop, or reports the refusal as
  issue + endpoint + capability and survives so the sync PR step still runs — never a silent pass
- **Test:** `tests/test_registry_change_issue.py::test_a_body_write_that_claims_success_but_never_sticks_fails_the_step`,
  `tests/test_registry_change_issue.py::test_a_refused_body_write_names_the_issue_the_endpoint_and_the_capability`

#### Scenario: the dry run previews the decision and writes nothing

- **Given** a store with no open marker issue, and one whose marker IS already open
- **When** `open_issue` runs with `dry=True`
- **Then** it returns `would create one issue` or `would update #<n>` and performs only the
  read-only marker search — never a body PATCH, label POST, create or edit
- **Test:** `tests/test_registry_change_issue.py::test_dry_run_mutates_nothing`,
  `tests/test_registry_change_issue.py::test_a_dry_update_of_a_marked_issue_does_not_label_it`
