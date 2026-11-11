# Stale-echo lanes and comment-list pagination

## A lane echoing a superseded sha is not a new fact

A lane can re-report the same stale head sha (e.g. `111e873c`/"base = origin/main tip")
five to seven times after you have already corrected it. Each echo arrives as "settled" and
looks like fresh state, but the API is truth: read the PR's live head/base
(`gh pr view N --json headRefOid,baseRefName,mergeStateStatus`). If the lane's cited
run binds to the stale head (`actions/runs/<id> --jq .head_sha`), the citation is superseded.

Once the correction is posted as the newest comment on the issue, **re-DMing or re-commenting
is a loop violation**. The lane's own claim protocol has it re-read the thread before its next
edit, so the correction will be seen. Stay silent; the durable board comment outranks every
echo. GH merges the PR's *current* head regardless of what number the lane quotes, so the
stale citation is harmless — do not escalate a sixth time.

## `--jq '.[-N:]'` on issue comments hides the newest comment

`gh api repos/{o}/{r}/issues/N/comments --jq '.[-N:]'` slices the FIRST page (default 30,
oldest-first). A comment you just POSTed (whose returned id is real) may be absent from that
slice even though it landed. This reads as "the POST failed silently" and lures a duplicate
repost.

Prove a comment landed with pagination instead:

```bash
gh api repos/{o}/{r}/issues/N/comments --paginate --jq '[.[]|.id]|.[-8:]'
# or
gh api -X GET "repos/{o}/{r}/issues/N/comments?per_page=100" --jq '[.[]|.id]|.[-8:]'
```

Do NOT pass `-f per_page=100` to a GET: `gh` sends it as a request body and the API returns
`422 "body wasn't supplied"`. Use `--paginate` or `-X GET` with a query string. Verify by
reading the exact id: `gh api repos/{o}/{r}/issues/comments/<id> --jq '.user.login, .created_at'`.
