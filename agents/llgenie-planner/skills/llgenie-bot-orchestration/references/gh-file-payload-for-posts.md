# `gh api -F` (uppercase) expands `@file`; `-f` (lowercase) does NOT

Posting an on-issue comment body from a file via `gh api`:
- `gh api .../comments -f body=@/tmp/x.md` → body becomes the LITERAL string `@/tmp/x.md` (lowercase `-f` does not expand `@file`). The comment is created but is a no-op record.
- `gh api .../comments -F body=@/tmp/x.md` → body is the file CONTENT (uppercase `-F` expands `@file`).

Why it matters: planner's durable on-issue records are the authoritative channel over DMs (which can be rejected/echo). An `@/tmp/...`-bodied comment looks like a valid record at the right id but carries no content — a silent hole in provenance.

Lesson: always use `-F body=@<file>` for file-backed comment bodies. If you ever need to fix one posted with `-f`, it can be repaired IN PLACE by PATCHing the same comment id with `-F body=@<file>` (id stays stable, content becomes real) — verify by reading `.body` back, not by trusting the POST exit code.

Verify the fix: read the comment `.body` from the API and confirm it does NOT start with `@/`. Length > 0 alone is not enough inside a parseable JSON body.

Reference: three records at ids 6663312883, 6663262043, 6663267676 were observed as literal `@/tmp/...` and repaired via PATCH with `-F`. (topic: planner comment posts)
