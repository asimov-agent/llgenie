# Posting and de-duplicating PR/issue comments

## Post a body containing brackets/quotes/code from a FILE, never inline in `-f body="…"`

A comment body with markdown task boxes (`- [ ]`), apostrophes, backticks, or `$` breaks an
inline `gh api …/comments -f body="…"` through the shell — `bash: eval: line N: unexpected EOF
while looking for matching '` — because the shell parses those characters before `gh` sees them.
Write the body to a file, then read it in with `$(cat)`, which passes the text as one argument:

    write_file /tmp/note.md   # the full body, verbatim
    gh api repos/<o>/<r>/issues/<n>/comments -f body="$(cat /tmp/note.md)" --jq '.id'

This keeps `- [ ]`, quotes, and code fences intact. Do not "escape" the body with a backslash
per character — that mangles it; the file path is the fix. Same for `gh pr edit --body-file`
(use the file flag directly).

### `-f body=@file` posts the LITERAL path — use `-F` or read with `$(cat)`

`gh api -f body=@/tmp/note.md` sends the fifteen-char string `@/tmp/note.md`, not the file's
contents: `-f`/`--raw-field` is a literal string and does **no** `@file` expansion. The comment
lands with the path as its body and you only notice on readback. Two correct forms:

- `gh api … -f body="$(cat /tmp/note.md)"` (shell reads the file; recommended, works everywhere), or
- `gh api … -F body=@/tmp/note.md` — capital `-F`/`--field` is the one that expands `@file`.

**`-f body=@-` (stdin) is the SAME trap** — `gh` does not expand `@-` for `-f`, so passing a
body via `subprocess.run(..., input=body)` with `-f body=@-` lands the literal two-char string
`@-`. The `gh api … -jq '.id'` still returns an id, so it reads as posted until you fetch the
comment's `.body` and see `@-`. To post from a Python string, write it to a file first and use
`-F body=@/path/file`; never rely on `-f body=@-` consuming stdin.

### Editing an existing comment: `PATCH …/issues/comments/<id>`, NOT under the issue

The update endpoint is `repos/<o>/<r>/issues/comments/<comment_id>` — the comment id sits
DIRECTLY under `issues`, with no `<issue_number>` segment. PATCHing
`repos/<o>/<r>/issues/<n>/comments/<id>` 404s. Build a clean JSON body-file with python (a
heredoc JSON gets polluted by shell interpolation) and pass `--input`:

    gh api -X PATCH repos/<o>/<r>/issues/comments/<id> --input /tmp/body.json

`--input` parses its file as **JSON**, so passing the raw markdown body file fails with
`Problems parsing JSON` (400). Simpler and equivalent: skip JSON entirely and update from a
plain-text body file with the expanding field form —
`gh api -X PATCH repos/<o>/<r>/issues/comments/<id> -F body=@/tmp/body.md`. Both reach the same
endpoint; `-F body=@file` is fewer moving parts when the body is already a markdown file.
Then read the comment's `.body` back and confirm its length/content — an edit that 404'd or a
`-f body=@file` literal both look "posted" until you read the actual text.

## A `queue_full`/`ambiguous` DM is NOT delivered — make the fact durable on-wire, never resend

`message_agent` can return delivery `ambiguous` with `queue_full` / "Live delivery admission
could not be confirmed … Do not resend." That is a hard signal the DM did not reach the peer
lane's live owner. Do NOT resend it (the queue is full; a resend also risks a duplicate once a
slot frees). Fall back to the DURABLE channel: post the same fact as a comment on the issue/PR
the work lives on (`gh api …/issues/<n>/comments -f body="$(cat /tmp/note.md)"`), so a stranger
and the next reader still get it. Note in your summary that the DM was `queue_full` and the fact
is recorded on the PR/issue id — an undelivered DM that only existed in chat does not exist.

## Never post the same comment through two tool paths in one turn

Running the same `gh pr comment` through BOTH `execute_code` and `terminal` in a
single turn posts TWO comments seconds apart. Both return an id, so nothing looks
wrong until you read the thread. Post a bookend/finish comment through ONE path
only, and read the id back once before moving on. If a result is unreadable, do
NOT re-issue in the same or next batch — a comment you cannot parse may already
have landed; establish state with an independent read first.

## Finding your own comment to de-duplicate: the list is paginated, oldest-first

The `issues/<n>/comments` endpoint defaults to 30 per page and returns
OLDEST-first. A PR with a long thread puts the duplicate you JUST posted on the
LAST page, so an unpaged `--jq '.[]'` silently omits it. Page explicitly and loop
until a short/empty page:

    for p in 1 2 3 4 5; do
      gh api "repos/<o>/<r>/issues/<n>/comments?per_page=100&page=$p" \
        --jq '.[]|select(.body|startswith("## ✅ Finish"))|{id,created_at,user:.user.login}'
    done

Quote the URL — an unquoted `&` makes the shell background the command and lose
the rest of the line. A Python loop over `subprocess.run(['gh','api', …])` is
safer than nesting `jq` quotes in bash (see terminal-and-guard-pitfalls.md).

## Never post a throwaway 'probe' comment just to test a write path

Posting a placeholder body (`FINISH-marker`, `test`, dummy text) to
`issues/<n>/comments` to confirm the endpoint accepts writes lands that nonsense on the
public PR/issue thread and has to be found and deleted. You do NOT need a write probe: the
create call's own response (a returned `id`/`html_url`) already proves the write path, and a
read (`gh api … --jq .body`) proves auth. If an accidental probe/junk comment does land, find
its id and remove it immediately:

    gh api repos/<o>/<r>/issues/<n>/comments \
      --jq '[.[]|select(.body|contains("<junk-marker>"))][0].id'   # page if long
    gh api -X DELETE repos/<o>/<r>/issues/comments/<id>

Then re-list to confirm it is gone. Never leave a placeholder comment in the audit trail.

## Delete the duplicate(s), keep exactly one of yours

Keep the EARLIER `created_at` of the identical pair; delete the rest:

    gh api -X DELETE repos/<o>/<r>/issues/comments/<id>

That endpoint deletes a comment on any issue OR PR. Then re-list once to prove
exactly one remains (a finish/bookend comment with no baseline or a duplicate is
the artefact the audit trail must not carry). Never delete another author's or the
gate bot's comment.
