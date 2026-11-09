# Posting a review body from a file

## The `-f` vs `-F` trap

`gh api -X POST repos/<o>/<r>/pulls/<n>/reviews -f "body=@/tmp/x.md"` stores the LITERAL string `@/tmp/x.md` as the review body — `-f` passes a raw string, so the `@path` file-substitution does not happen. The call still exits 0, so a create that looks successful can carry a junk body.

Use `-F "body=@/tmp/x.md"` (capital F) to read the file, or `--input` with a JSON payload. Always read the written body back (`gh api .../reviews/<id> --jq .body`) to confirm the content landed, not the path.

## Review bodies are editable after submit

A submitted review body is **not** immutable. Correct a wrong body in place without deleting/re-creating:

```
gh api -X PUT repos/<o>/<r>/pulls/<n>/reviews/<id> -f "body=$(cat /tmp/x.md)"
```

Then confirm `.body`, `.state` and `.commit_id` on the same id. `state` is `COMMENTED` / `APPROVED` / `CHANGES_REQUESTED`; the REST create enum is `COMMENT`, `APPROVE`, `REQUEST_CHANGES` (not `COMMENTED`) — value passed via `-f event=...`.

## Belt-and-suspenders record

When the review body matters as load-bearing state, also post the same verdict as an issue comment (`gh api -X POST .../issues/<n>/comments -F "body=@file"`) so the content survives even if the review object is later edited or dismissed. Cite the review id in that comment.
