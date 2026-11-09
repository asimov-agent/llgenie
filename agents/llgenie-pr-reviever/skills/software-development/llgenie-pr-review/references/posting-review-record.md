# Posting the durable review record

## Write the body to a file; never inline a heredoc

A review body that carries markdown and backticks (``code``, `$(...)`, `` `gh ...` ``) must be written to a file and posted with `--body-file`. An inline shell heredoc runs the text through command substitution: backticks execute, `$(...)` expands, quotes strip out — the posted body is not the body you typed. The failure is silent (the command exits 0) and only shows up when a reader opens the comment.

```
write_file path=/tmp/review_<id>.md   # full markdown body
gh pr comment <n> -R <owner/repo> --body-file /tmp/review_<id>.md
git show <sha>:<path>                # when quoting file lines, read the blob, not echo
```

The same applies to `gh pr review --body-file`, `gh issue comment --body-file`, and `gh pr edit --body-file`. Use a per-review temp path so a concurrent review does not overwrite another body.

## `gh api` POSTs a file body only with `-F`; `-f` sends the literal `@path`

`gh api -f body=@/tmp/body.md` publishes the six characters `@/tmp/body.md` as the body — `-f`
(string field) never expands a leading `@`. Only `-F` triggers file reads. The request exits 0, the
object is created, and the only signal is the body itself:

```
gh api -X POST repos/<o>/<r>/issues/<n>/comments  -F body=@/tmp/body.md   # reads the file
gh api -X POST repos/<o>/<r>/issues/<n>/comments  -f body=@/tmp/body.md   # WRONG: literal path
```

Read `.body` back on the created object before reporting the record posted. When a literal path
lands on an issue/numbered comment, `PATCH /repos/<o>/<r>/issues/comments/<id>` with the real body.

## Creating a review over REST: `event` is the input, `state` is the output

`POST /repos/<o>/<r>/pulls/<n>/reviews` takes `commit_id`, `event`, `body`. The accepted `event`
values are `APPROVE`, `REQUEST_CHANGES` and `COMMENT` — passing `COMMENTED` (the value the object
*returns* as `state`) is rejected with `422 … event: Invalid request`.

```
gh api -X POST repos/<o>/<r>/pulls/<n>/reviews \
  -f commit_id=<head-sha> -f event=COMMENT -F body=@/tmp/review_<id>.md
```

A submitted review body is not frozen: `PUT /repos/<o>/<r>/pulls/<n>/reviews/<id>` with `body`
rewrites the summary in place, keeping `id`, `state` and `submitted_at` — the repair for a body that
posted as a literal path or a blank field, and better than leaving a stub review or filing a second
one. Read back `{id,state,commit_id,body}` after the PUT and confirm the state is the one you also
(correctly) intended to raise; a COMMENTED review is a record, not an approval.


## A successful post is not proof of content — read it back

`gh ... comment` exits 0 when the request was accepted; it does not prove the posted text, author or timestamp. Immediately read the object back and assert the facts you rely on:

```
gh api repos/<owner>/<repo>/issues/<n>/comments \
  --jq '.[] | select(.body|test("<unique phrase from the body>")) | {id,created_at,user:.user.login}'
```

Report the id and the timestamp from the read-back, not from the command's stdout.

## Re-read the head before you post a verdict or a record

The head moves mid-review (a fix push, a force-push rebase, a follow-up commit). A verdict, a write-back, or a "green at head" record measured at an older head is stale by definition. Before finalizing, re-read the current head from the API and, if it differs, say so and re-measure at the new head rather than letting the old record stand:

```
gh pr view <n> -R <owner/repo> --json headRefOid,mergeStateStatus --jq '{h:.headRefOid,m:.mergeStateStatus}'
gh api repos/<owner>/<repo>/pulls/<n> --jq .head.sha      # cross-check
```

A local tracking ref (`origin/pr<n>`) can lag a force-push; `git fetch --force origin refs/pull/<n>/head:refs/remotes/origin/pr<n>` when the API head and your local ref disagree.

## Post the verification record on the SOURCE issue, not only the channels a dispatch cites

A dispatch often names channels to mirror a record onto ("record on #A and #B"), but the **source
acceptance/AC issue** that the guard and the close actually read is frequently a THIRD issue the
dispatch never lists. Posting only to the cited channels leaves the source bare, so the record does
not exist where the board closes the work. Post on the source AC issue itself as well, and mirror to
every cited channel — then read each id back (single copy, correct target) before claiming done. The
verifying comment belongs on the issue whose criterion it evidences, not merely where a routing note
happened to point.

## This lane's record is COMMENTED, never APPROVE

When the PR author is the token (self-PR), GitHub refuses a self-approval and the record must be a `COMMENTED` review/comment carrying the verdict line (head sha + run id + green/not-green). Never `-a`/approve, never merge, never arm auto-merge on a self-PR — the verdict is a statement, not an authorisation.
