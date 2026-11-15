# registry-review-publish-rest

## Why

`scripts/registry_review.py::publish` (the registry-sync-review lane's
`make registry-review-publish`) updates the review issue's body with
`gh issue edit --body` — a GraphQL `updateIssue` mutation. PR #2673 measured on
the sibling lane (`registry_change_issue.py`, registry-sync run 43577357338)
that the runner's fine-grained owner PAT (`secrets.BUMP_TOKEN`) is refused by
exactly this transport (`GraphQL: Resource not accessible by personal access token
(updateIssue)`), while the same credential writes issues over REST fine.

This lane today runs on `github.token` (registry-sync-review.yml:62/:102), which
GraphQL accepts — so there is no measured failure yet — but the transport is the
known-refused one, and the call has neither the refused-403 handling nor the
write-read-back proof its sibling gained in #2673.

## How

- Switch `publish`'s body update from the GraphQL `gh issue edit` call to the
  REST seam `gh api -X PATCH repos/<slug>/issues/<n> -f body=...` (the
  #2673/#826/#775 class). Creating `--label` stays as is unless its own drop is
  measured.
- Read the body back over the same REST transport and fail the step (naming the
  issue) when the stored body is not what the write sent — the #819 silent-drop
  red.
- On a refused 403 ("HTTP 403" / "not accessible by personal access token"),
  print one loud line naming the issue, the endpoint, and the missing capability,
  and survive (the #775 credential-fact rule).

## Impact

Both registry lanes survive any runner credential. Review bodies are proven
stored, not assumed. Refusals report instead of tracebacks.

Not in this change: the sibling lane's own body edit (it has its own body-edit
transport and its own marker; moving it is a separate change), and the
`--label` create flag's possible drop (only handled if separately measured).

## References

- Issue: #2691 (this change). Source pattern: PR for #2673
  (`scripts/registry_change_issue.py` REST read-back seam) and #775/#826.
