# registry-sync-review

## MODIFIED Requirements

### Requirement: the review issue body is updated over REST and proven stored

`publish` SHALL update an existing review issue's body through the REST seam
`gh api -X PATCH repos/<slug>/issues/<n> -f body=...` — never through the
GraphQL `gh issue edit` transport. After the write it SHALL read the body back
over the same REST endpoint and fail the step (naming the issue) when the stored
body is not exactly what the write sent. A write GitHub refuses outright with
`HTTP 403` / `not accessible by personal access token` SHALL print one loud line
naming the issue, the endpoint and the missing capability and return without
raising.

WHEN `publish` edits an existing review issue,
THEN the body update goes over REST and is proven by a read-back that must equal
the body written, and a 403 refusal is reported rather than raised.

#### Scenario: the body update uses the REST PATCH seam and reads the body back
Given an open issue carrying this store's review marker
When  `publish` runs to update it
Then  a `gh api -X PATCH repos/<repo>/issues/<n> -f body=...` call is made (no
      `issue edit`, so the GraphQL transport is never touched) and the stored
      body is read back and equals what was written.

- **Test:** `tests/test_registry_review.py::test_a_second_publish_edits_over_rest_and_reads_the_body_back`

#### Scenario: a body that did not stick reds the step, naming the issue
Given the read-back returning a body different from what the write sent
When  `publish` runs its update
Then  the step fails naming the issue — a 0-exit write that never stored must
      never look green.

- **Test:** `tests/test_registry_review.py::test_an_update_whose_body_did_not_stick_fails_naming_the_issue`

#### Scenario: a refused body write is reported, not raised
Given the REST write answering a 403 "not accessible by personal access token"
When  `publish` runs its update
Then  one loud line names the issue, the endpoint and the missing capability and
      the run survives (returns a result) instead of tracebacking.

- **Test:** `tests/test_registry_review.py::test_a_refused_body_write_reports_and_survives`
