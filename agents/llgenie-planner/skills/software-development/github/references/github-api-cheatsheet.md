# GitHub REST API Cheatsheet

Base URL: `https://api.github.com`

All requests need: `-H "Authorization: token $GITHUB_TOKEN"`

Use the `gh-env.sh` helper to set `$GITHUB_TOKEN`, `$GH_OWNER`, `$GH_REPO` automatically:
```bash
source "${HERMES_HOME:-$HOME/.hermes}/skills/github/github-auth/scripts/gh-env.sh"
```

## Repositories

| Action | Method | Endpoint |
|--------|--------|----------|
| Get repo info | GET | `/repos/{owner}/{repo}` |
| Create repo (user) | POST | `/user/repos` |
| Create repo (org) | POST | `/orgs/{org}/repos` |
| Update repo | PATCH | `/repos/{owner}/{repo}` |
| Delete repo | DELETE | `/repos/{owner}/{repo}` |
| List your repos | GET | `/user/repos?per_page=30&sort=updated` |
| List org repos | GET | `/orgs/{org}/repos` |
| Fork repo | POST | `/repos/{owner}/{repo}/forks` |
| Create from template | POST | `/repos/{owner}/{template}/generate` |
| Get topics | GET | `/repos/{owner}/{repo}/topics` |
| Set topics | PUT | `/repos/{owner}/{repo}/topics` |

## Pull Requests

| Action | Method | Endpoint |
|--------|--------|----------|
| List PRs | GET | `/repos/{owner}/{repo}/pulls?state=open` |
| Create PR | POST | `/repos/{owner}/{repo}/pulls` |
| Get PR | GET | `/repos/{owner}/{repo}/pulls/{number}` |
| Update PR | PATCH | `/repos/{owner}/{repo}/pulls/{number}` |
| List PR files | GET | `/repos/{owner}/{repo}/pulls/{number}/files` |
| Merge PR | PUT | `/repos/{owner}/{repo}/pulls/{number}/merge` |
| Request reviewers | POST | `/repos/{owner}/{repo}/pulls/{number}/requested_reviewers` |
| Create review | POST | `/repos/{owner}/{repo}/pulls/{number}/reviews` |
| Inline comment | POST | `/repos/{owner}/{repo}/pulls/{number}/comments` |

### PR Merge Body

```json
{"merge_method": "squash", "commit_title": "feat: description (#N)"}
```

Merge methods: `"merge"`, `"squash"`, `"rebase"`

### PR Review Events

`"APPROVE"`, `"REQUEST_CHANGES"`, `"COMMENT"`

## Issues

| Action | Method | Endpoint |
|--------|--------|----------|
| List issues | GET | `/repos/{owner}/{repo}/issues?state=open` |
| Create issue | POST | `/repos/{owner}/{repo}/issues` |
| Get issue | GET | `/repos/{owner}/{repo}/issues/{number}` |
| Update issue | PATCH | `/repos/{owner}/{repo}/issues/{number}` |
| Add comment | POST | `/repos/{owner}/{repo}/issues/{number}/comments` |
| Add labels | POST | `/repos/{owner}/{repo}/issues/{number}/labels` |
| Remove label | DELETE | `/repos/{owner}/{repo}/issues/{number}/labels/{name}` |
| Add assignees | POST | `/repos/{owner}/{repo}/issues/{number}/assignees` |
| List labels | GET | `/repos/{owner}/{repo}/labels` |
| Search issues | GET | `/search/issues?q={query}+repo:{owner}/{repo}` |

Note: The Issues API also returns PRs. Filter with `"pull_request" not in item` when parsing.

## CI / GitHub Actions

| Action | Method | Endpoint |
|--------|--------|----------|
| List workflows | GET | `/repos/{owner}/{repo}/actions/workflows` |
| List runs | GET | `/repos/{owner}/{repo}/actions/runs?per_page=10` |
| List runs (branch) | GET | `/repos/{owner}/{repo}/actions/runs?branch={branch}` |
| Get run | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}` |
| Download logs | GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/logs` |
| Re-run | POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/rerun` |
| Re-run failed | POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs` |
| Trigger dispatch | POST | `/repos/{owner}/{repo}/actions/workflows/{id}/dispatches` |
| Commit status | GET | `/repos/{owner}/{repo}/commits/{sha}/status` |
| Check runs | GET | `/repos/{owner}/{repo}/commits/{sha}/check-runs` |

## Releases

| Action | Method | Endpoint |
|--------|--------|----------|
| List releases | GET | `/repos/{owner}/{repo}/releases` |
| Create release | POST | `/repos/{owner}/{repo}/releases` |
| Get release | GET | `/repos/{owner}/{repo}/releases/{id}` |
| Delete release | DELETE | `/repos/{owner}/{repo}/releases/{id}` |
| Upload asset | POST | `https://uploads.github.com/repos/{owner}/{repo}/releases/{id}/assets?name={filename}` |

## Secrets

| Action | Method | Endpoint |
|--------|--------|----------|
| List secrets | GET | `/repos/{owner}/{repo}/actions/secrets` |
| Get public key | GET | `/repos/{owner}/{repo}/actions/secrets/public-key` |
| Set secret | PUT | `/repos/{owner}/{repo}/actions/secrets/{name}` |
| Delete secret | DELETE | `/repos/{owner}/{repo}/actions/secrets/{name}` |

## Branch Protection

| Action | Method | Endpoint |
|--------|--------|----------|
| Get protection | GET | `/repos/{owner}/{repo}/branches/{branch}/protection` |
| Set protection | PUT | `/repos/{owner}/{repo}/branches/{branch}/protection` |
| Delete protection | DELETE | `/repos/{owner}/{repo}/branches/{branch}/protection` |

## Git refs (branches and tags)

| Action | Method | Endpoint |
|--------|--------|----------|
| List refs by prefix | GET | `/repos/{owner}/{repo}/git/matching-refs/heads/{prefix}` |
| Get one ref | GET | `/repos/{owner}/{repo}/git/ref/heads/{branch}` |
| Create ref | POST | `/repos/{owner}/{repo}/git/refs` (`{"ref":"refs/heads/x","sha":"<sha>"}`) |
| Update/force ref | PATCH | `/repos/{owner}/{repo}/git/refs/heads/{branch}` |
| Delete ref | DELETE | `/repos/{owner}/{repo}/git/refs/heads/{branch}` |

**Every ref comes back FULLY qualified** (`refs/heads/ci/fix-thing`), and `matching-refs` matches by string
PREFIX, so a prefix containing slashes (`ci/data-gap-`) is legal. Strip only `refs/heads/`
(`ref.removeprefix("refs/heads/")`) — `rsplit("/", 1)[-1]` throws away every intermediate segment and a
prefix comparison then never matches. Creating a ref through the API fires no `push` workflow, which makes a
throwaway ref a quiet way to probe a branch-reading code path (create, run the target, delete).

`refs/heads/<prefix>` returns `[]` (not 404) when nothing matches, so an empty result is indistinguishable
from a failed read unless you check the exit status — never coalesce both into "none".

## User / Auth

| Action | Method | Endpoint |
|--------|--------|----------|
| Get current user | GET | `/user` |
| List user repos | GET | `/user/repos` |
| List user gists | GET | `/gists` |
| Create gist | POST | `/gists` |
| Search repos | GET | `/search/repositories?q={query}` |

## `gh api -f` on a GET endpoint can 404 while the same params in a URL string succeed

`gh api <path> -f key=value` sends the fields as a **form body**, and some GET
list endpoints reject that form with a bare `HTTP 404 Not Found` — even for a
resource that exists and returns 200 unfiltered. Measured on
`GET /repos/{owner}/{repo}/actions/runs` (gh 2.103.3): `-f head_sha=… -f event=pull_request`
returned 404 for every head (open, merged, known-good), while the identical params
as a **raw URL query string** returned 200 with the correct `total_count`. The
unfiltered path also returned 200.

Rule: for GET endpoints that filter, put params in the URL string
(`gh api "repos/o/r/actions/runs?head_sha=<sha>&event=pull_request&per_page=1"`),
not `-f`. Reserve `-f`/`-F` for POST/PATCH bodies. Treat a filtered-query 404 as
suspect until reproduced both ways: confirm which invocation the code actually
uses before blaming the server. A script passing `-f` to a GET filter will fail
loud/empty nondeterministically across gh versions — that is the query form, not
the data.

## `gh api` has no `--json` — it is `--jq`/`-q` (the `--json` flag belongs to `gh pr|issue|run view`)

Two different gh families get mixed up under time pressure. `gh pr view`/`gh issue view`/`gh run view`
take `--json <fields>` plus `--jq <filter>`; **`gh api` takes neither `--json` nor `-q`'s sibling
selector** — it always returns the full JSON body and only accepts `--jq`/`-q` to filter it. Running
`gh api repos/o/r/pulls/1 --json state` prints gh's entire usage text and exits non-zero, which in a
long probe chain reads like "the call returned nothing". Correct forms:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '.state'          # filter the full body
gh api repos/<o>/<r>/pulls/<n> | jq '.state'          # or pipe to jq (same result)
gh pr view <n> --json state --jq .state               # --json is a `view` flag, not an `api` one
```

Also note `gh api` rejects `--json` on the *subcommand* level, so a wrapper that appends `--json` to
both families breaks only the `api` calls — and those failures are silent empties once stderr is
piped. When a batched probe returns blank, re-run one `gh api` call bare (no `--jq`) to tell a flag
error from genuinely empty data.

## Array-valued fields (`labels`, `assignees`, `reviewers`) need `--input`, never `-f`/`-F`

`-f key=value` always sends a **string**, and `-F 'key=["a","b"]'` is not a typed array either.
Patching an array field that way is rejected with `422 … For 'properties/labels', "" is not an array`
or `… '["parked"]' is not an array` — the mutation never lands. Because `gh` prints the error while
the call still exits through a pipeline, it reads like a silent no-op and invites a retry loop.
Send the whole body as JSON:

```bash
printf '{"labels":["parked"]}\n' > /tmp/p.json
gh api --method PATCH repos/<o>/<r>/issues/<n> --input /tmp/p.json \
  --jq '(.number|tostring)+" labels="+([.labels[].name]|join(","))'
```

- **A PATCH carrying `labels:[...]` REPLACES the whole set** — to keep a label, include it; to clear
  all, send `{"labels":[]}`.
- Read the set back bare (`gh api repos/<o>/<r>/issues/<n> --jq '[.labels[].name]'`). A PATCH that
  exits 0 is not proof the label set changed until you re-read it; a 422 is proof it did not.
- Same rule for `assignees` and `reviewers` bodies (and `{"names":[...]}` on the labels sub-endpoint).

## `check-runs[].id` is a CHECK-RUN id, not a workflow-run id

`GET /commits/<sha>/check-runs` returns `.check_runs[].id`, which is **not** accepted by
`/actions/runs/<id>` or `/actions/runs/<id>/jobs` — both return a bare `404 Not Found`, which reads
exactly like "this run does not exist". To go from a failing check to its producing run, use the
check-run's own `details_url`:

```bash
gh api repos/<o>/<r>/check-runs/<check_run_id> --jq '{name,head_sha,details:.details_url}'
# details_url ends in /actions/runs/<run_id>/job/<job_id> — read the run id out of the URL
```

`/commits/<sha>/check-runs` gives names + conclusions + check-run ids; it never gives you run ids.

## Pagination

Most list endpoints support:
- `?per_page=100` (max 100)
- `?page=2` for next page
- Check `Link` header for `rel="next"` URL

### `.[-1]` / `.[-5:]` on a list is NOT "the newest" unless you paginate

`gh api .../issues/<n>/comments` (and every list endpoint) returns only the FIRST page — 30 items by
default — oldest-first. So `--jq '.[-1].id'` gives the newest comment **of page one**, and `length`
returns `30` the moment the true count is 30 or more. A just-posted comment with a fresh id is then
absent from `.[-1]` and from `.[-5:]`, which reads exactly like "my POST didn't land" — the classic
false alarm. Measured: `length` was exactly `30`, the newest comment sat on page two, and only
`--jq '[.[]|.id]'` with `per_page=100` revealed it as the true last id.

Rules:
- To see the newest item, always pass `?per_page=100` (via the **URL string**, not `-f` — see the
  GET-body 404 note above) and, past 100 items, follow the `Link: rel="next"` chain
  (`gh api --paginate "repos/o/r/issues/N/comments?per_page=100"`).
- Treat `length == 30` (or any exact multiple of the page size) as "there may be more", never as the total.
- Verify a POST by fetching its **returned id directly** (`gh api repos/o/r/issues/comments/<id>`), not
  by looking for it at `.[-1]` — the direct GET is the only unambiguous proof the mutation persisted.
- `-f per_page=100` on a **GET** sends a form body and 422s (`"body" wasn't supplied`); put the param in
  the URL query string instead.

### `sort=`/`direction=` are NOT honored on issue comments — the list is always oldest-first

`GET /issues/<n>/comments?per_page=1&sort=created&direction=desc` still returns the **oldest** comment,
not the newest. The issue-comments endpoint ignores `sort`/`direction` entirely, so `.[0]` is the first
comment ever posted and a "newest comment" probe built on `per_page=1&direction=desc` reports a
nine-minute-stale id as current — which reads exactly like "my reply is not there". Read the newest from
the full ascending page (`?per_page=100` + `.[-1]`), or GET the specific comment id. Do not trust a
`direction=desc` read-back on this endpoint.

**`-f body=@file` posts the LITERAL string `@file`, not the file's contents — only `-F` reads a file.**
`gh api .../comments -f body=@/tmp/x.md` exits 0 and creates a comment whose entire body is the path
string `@/tmp/x.md` (measured: a dispatch comment landed as literally `@/tmp/pl1686_dispatch.md`, so the
implementer was told a dispatch existed but saw only a path). The `-f`/`--raw-field` flag is
string-literal by design; the file-magic `@` prefix works ONLY with the typed `-F`/`--field` flag. Use
`-F body=@body.md` for content from a file, `-f body="plain text"` for inline. After any such POST,
read it back (`gh api .../issues/comments/<id> --jq '.body|.[0:60]'`) — the `-f`-with-`@` slip is silent
and only the read-back shows the literal path.

Related: post long or markdown-heavy bodies from a file rather than an escaped shell string —
`gh api repos/<o>/<r>/issues/<n>/comments -F body=@body.md` (and `gh issue create --body-file body.md`).
The file goes verbatim, so headings and code fences survive; an inline quoted body is where `##` markers
and backticks get mangled. Validate a body file's headings by reading it back before posting.

### A `--jq` cast error after a POST does NOT mean the write failed

`gh api -X POST ... --jq '"comment="+.id'` exits 1 with `cannot add: string ("comment=") and number
(6586810622)` — but the comment **did land**. The POST succeeded; only the jq filter that builds the
summary string blew up, because `+` on a string and a **number** (or `null`/bool) is a type error. Two
consequences:

- **Build labels with interpolation, not `+`.** `--jq '"comment=\(.id)"'` or `(.id|tostring)` casts
  anything to text; `"..."+.field` is only safe when `.field` is already a string (`.state`, or
  `.merged_at//"never"` with the `//` default); every id, count, number and un-defaulted nullable
  needs the cast.
- **Verify the mutation by direct GET of the id the POST returned, never by whether the jq printed.**
  A non-zero exit from `C=$(gh api -X POST ... --jq '...')` can be pure jq, with the write already
  persisted. `gh api repos/<o>/<r>/issues/comments/<id> --jq '.id'` is the only unambiguous proof.
  Reporting "my POST didn't land" off a jq error files a false alarm and invites a duplicate write.

## Rate Limits

- Authenticated: 5,000 requests/hour
- Check remaining: `curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit`

## Common curl Patterns

```bash
# GET
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$GH_OWNER/$GH_REPO

# POST with JSON body
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$GH_OWNER/$GH_REPO/issues \
  -d '{"title": "...", "body": "..."}'

# PATCH (update)
curl -s -X PATCH \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$GH_OWNER/$GH_REPO/issues/42 \
  -d '{"state": "closed"}'

# DELETE
curl -s -X DELETE \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$GH_OWNER/$GH_REPO/issues/42/labels/bug

# Parse JSON response with python3
curl -s ... | python3 -c "import sys,json; data=json.load(sys.stdin); print(data['field'])"
```
