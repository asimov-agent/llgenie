## ADDED Requirements

### Requirement: The change-issue body write uses the REST transport

The registry-sync change-issue leg (`scripts/registry_change_issue.py::open_issue`, run by `make sync-change-issue`) SHALL update an existing change issue's body through the REST endpoint (`gh api -X PATCH repos/<slug>/issues/<n> -f body=...`) and SHALL NOT invoke `gh issue edit --body`, because the leg's runner credential (a fine-grained owner PAT) is refused by the GraphQL `updateIssue` mutation while the same credential writes issues over REST.

#### Scenario: an existing change issue is updated over REST

- **WHEN** `open_issue` finds an open issue carrying this store's marker and updates it
- **THEN** the update is a `gh api -X PATCH repos/<slug>/issues/<n>` call carrying the new body, and no `gh issue edit` call is made

#### Scenario: the registry-sync run ships the updated body

- **WHEN** the registry-sync workflow runs the `State what changed in ONE issue` step at a head whose store differs from `HEAD`
- **THEN** the step exits 0 and the change issue's body carries the new store's marker, proven by a completed run

### Requirement: The body write is proven by read-back

After the PATCH the leg SHALL read the issue body back over the same REST transport and fail the step (naming the issue) when the read-back does not contain the marker the write claimed to store — a write that claims success but never sticks must not look green.

#### Scenario: a body write that never sticks fails the step

- **WHEN** the PATCH exits 0 but the issue body read back from the tracker lacks this store's marker
- **THEN** the leg exits non-zero naming the issue number

### Requirement: A refused body write is reported loudly with issue, endpoint, and capability

When the body PATCH is refused outright by the credential (HTTP 403 / `not accessible by personal access token`), the leg SHALL print one stderr line naming the issue number, the REST endpoint, and the missing capability, and SHALL return without an exception — a credential refusal is a fact that retry cannot fix, and dying on it would forfeit the sync PR the run exists to produce.

#### Scenario: refusal is named, not a traceback

- **WHEN** the credential refuses the body PATCH with a 403 refusal
- **THEN** stderr names the issue, the `repos/<slug>/issues/<n>` endpoint and the issues-write capability, and the leg survives (no exception), while any other `gh` failure still raises
