## ADDED Requirements

### Requirement: The review issue body write is REST-only and proven by read-back

`scripts/registry_review.py` SHALL update a review issue's body only over the REST surface
(`gh api -X PATCH repos/<slug>/issues/<n> -f body=...`) and SHALL NOT call `gh issue edit --body`
(the GraphQL `updateIssue` mutation the registry lane's runner credentials are refused by —
measured for the sibling leg on registry-sync run 43577357338, issue #2673). After a successful
PATCH it SHALL read the body back over the same REST transport and fail the step (naming the
issue) when the stored body is not the body the write sent. A refused write (HTTP 403 /
"not accessible by personal access token" class) SHALL print one stderr line naming the issue,
the endpoint and the required issues-write capability, and `publish` SHALL return
`update refused for #<n>` without raising.

#### Scenario: a re-publish edits the marked issue over REST and proves the body

- **WHEN** an open issue carries the store's review marker and `publish` runs again
- **THEN** no `issue edit` call is made; a `PATCH repos/<slug>/issues/<n>` carrying `body=` runs,
  the body is read back with `--jq .body`, and the stored body equals the body that was sent

#### Scenario: a body write that claims success but never stores fails the step

- **WHEN** the PATCH exits 0 but the read-back body is not the body that was sent
- **THEN** the step fails (SystemExit) naming the issue whose body never changed

#### Scenario: a refused body write is reported, not a traceback

- **WHEN** the PATCH is refused with the personal-access-token 403 refusal
- **THEN** stderr names the issue number, the `repos/.../issues/<n>` endpoint and the issues-write
  capability, `publish` returns `update refused for #<n>`, and no exception escapes
