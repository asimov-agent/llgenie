# registry-review-publish-rest — the review body edit moves to the REST seam

Date: 2026-11-15. Implements issue #2691.

## What and why

`scripts/registry_review.py::publish` (the registry-sync-review lane's
`make registry-review-publish`) updated an existing review issue's body with
`gh issue edit --body` — a GraphQL `updateIssue` mutation. PR #2673 measured on
the sibling lane (`registry_change_issue.py`, registry-sync run 43577357338)
that the runner's fine-grained owner PAT is refused by exactly this transport
while the same credential writes issues over REST fine. This lane ran on
`github.token`, so there was no measured failure yet — but the transport was the
known-refused one, and the call carried neither the refused-403 handling nor the
write-read-back proof its sibling gained in #2673.

## What changed

- `scripts/registry_review.py`:
  - `publish` now updates an existing review issue's body through the REST seam
    `_edit_body` → `gh api -X PATCH repos/<slug>/issues/<n> -f body=...` (mirroring
    `registry_change_issue.py`'s `repo_slug` / `_gh_api` / `_REFUSED` shape), never
    the GraphQL `gh issue edit`.
  - The step reads the body back over the same REST endpoint and fails with
    `SystemExit` naming the issue when the stored body != the body written — the
    #819 silent-drop guard, so a 0-exit write that never stored cannot look green.
  - A refused write (`HTTP 403` / `not accessible by personal access token`) prints
    one loud `stderr` line naming issue + endpoint + capability and returns,
    surviving the lane (the #775 credential-fact rule). Every other gh failure
    still raises.
- `tests/test_registry_review.py`: the duplicate-publish test now asserts the REST
  PATCH and read-back (no `issue edit`); new tests pin the silent-drop `SystemExit`
  and the refused-write survival, each with `# Given / # When / # Then`.
- OpenSpec: `openspec/changes/registry-review-publish-rest/` (proposal, spec,
  tasks, `.openspec.yaml`).

## Verified against the spec

- `scripts/registry_review.py` contains no `"issue", "edit"` call:
  `grep -n '"issue", "edit"' scripts/registry_review.py` exits 1.
- The body update is proven by a read-back that compares against the exact body
  written: `test_a_second_publish_edits_over_rest_and_reads_the_body_back`.
- A refused body write reports issue + endpoint + capability and does not raise:
  `test_a_refused_body_write_reports_and_survives`; the silent-drop red is
  `test_an_update_whose_body_did_not_stick_fails_naming_the_issue`.
- `make test-unit` pass (run id recorded in the PR), `make openspec-tasks-check`
  green on the completed `tasks.md`.

## Out of scope

The sibling lane's own body edit (`registry_change_issue.py:340` still uses the
GraphQL `gh issue edit --body` for its marker-keyed body) is its own transport and
its own marker; moving it is a separate change, not folded here. Not covered in
this issue/PR.
