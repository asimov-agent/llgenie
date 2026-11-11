# Filing an issue or PR: prove absence, then prove the created number

## The failure this prevents

A tracker-absence search that *errors* returns empty output, which reads exactly like
"no tracker exists". Filing on that evidence produces a duplicate. Worse, `gh issue create`
can succeed while its printed URL fails a downstream `grep`/`tail`, so a retry of the
"failed" command files a **second** issue seconds later, byte-identical to the first.

Two invocations, two issues, one diagnosis — the board now has two vehicles and the
planner has to spend a turn reconciling them.

## Procedure

1. **Search with a command that fails loudly.** A `| jq` that cannot parse the response is
   a failed search, not an empty one. Require both a zero exit code AND a parsed
   `total_count`/array before believing "absent":

   ```bash
   gh api -X GET search/issues \
     -f q='repo:OWNER/REPO is:issue in:title "<3-6 distinctive title words>"' \
     --jq '.total_count' || { echo 'SEARCH FAILED — do not file'; exit 1; }
   ```

   If the query errors or prints nothing, re-run it a different way (title words, recent
   `gh issue list --limit 20 --search`) before filing. Never file on an errored search.

2. **Create once, and capture the URL from a command whose output you inspect directly.**
   Do not pipe the create through `grep -oE '#[0-9]+'` / `tail -n 2` and then judge
   success by whether the filter matched — the create already happened. Run the create
   alone, then verify:

   ```bash
   gh api repos/OWNER/REPO/issues?state=all\&sort=created\&direction=desc\&per_page=5 \
     --jq '.[]|"\(.number) \(.created_at) \(.title)"' | head -5
   ```

   The newest issue by you should be the one you just filed, with the exact title.

3. **If a create's output is ambiguous, verify before retrying.** Never retry a create until
   the list in step 2 shows it did not land. An empty grep is not evidence of failure.

## If a duplicate already exists

Pick one vehicle on measured merit, close the other with an explicit comparison table
(body/ACs/labels/claim state), state that the diagnosis is **not** rejected, and point the
surviving issue at the closed one (comment id) so the next reader follows one trail.
Keep the vehicle that already carries the dispatch/DM trail — moving routing is more
costly and more confusing than swapping numbers.

Never delete or edit the duplicate's body to hide the error; disclose the root cause
(errored search, ambiguous create output) in the closing comment.

## Labels and body transport

A label that does not exist makes `gh issue create` exit non-zero **before** the issue is created
(`could not add label: 'docs' not found`) — so the retry is safe, but still run the step-2
newest-issue check afterwards rather than assume the first attempt left nothing behind. List the real
names once (`gh label list -L 100 --json name --jq '.[].name'`) and use one from that set; a guessed
`docs`/`bug` that is absent costs a whole create round-trip.

Pass long bodies with `--body-file`, never an inline `--body` or heredoc: backticks and `$VAR` inside
the text are shell-expanded or break the quoting, producing a mangled or empty body that only shows
up when a later gate reads it.

```bash
gh issue create --repo <o>/<r> --title '<title>' --body-file /tmp/issue-body.md -l agent:implement
```

File refined, implementable work with both `agent:refined` and `agent:implement` set
at creation time, and verify them back off the API — a created issue with no labels is
invisible to every dispatch sweep.
