# Registry review publish: body-edit the review issue over REST, not GraphQL

## Why

`scripts/registry_review.py::publish` updates the store's review issue body with
`gh issue edit --body` (line ~311) — the GraphQL `updateIssue` mutation that the registry lane's
runner credential is refused by. PR for issue #2673 measured exactly this transport failing on the
sibling leg (`registry_change_issue.py`, registry-sync run 43577357338: `GraphQL: Resource not
accessible by personal access token (updateIssue)`), and the same credential writes issues over
REST without refusal. This lane today runs on `github.token` (which GraphQL accepts), so there is
no measured failure yet — the defect is latent: one credential change away from freezing every
review issue body at its creation text, and the call carries neither the refused-403 handling nor
the write-read-back proof its sibling gained in #2673. Issue #2691.

## What Changes

- `publish` body-updates through a REST seam `gh api -X PATCH repos/<slug>/issues/<n> -f body=...`
  (new `_edit_body` + `_gh_api` + `repo_slug` in `registry_review.py`, mirroring the proven
  `registry_change_issue.py` seam), never through `gh issue edit`.
- After the PATCH the exact body is read back over the same transport; a body that does not match
  (silent drop, the #819 class) fails the step naming the issue.
- A refused write (HTTP 403 class) prints one stderr line naming issue + endpoint + required
  capability, and `publish` returns `update refused for #N` instead of raising.
- Tests: the fake `gh` refuses any `issue edit` transport call; update test asserts PATCH +
  read-back + stored equality; two new tests pin silent-drop failure and the refusal report.

## Impact

- Affected specs: `registry-sync-review` (publish transport requirement ADDED)
- Affected code: `scripts/registry_review.py`, `tests/test_registry_review.py`
- No workflow wiring change (this lane stays on `github.token`; the fix is transport-only, so it
  survives a future credential change). Out of scope: filing under a different secret.
