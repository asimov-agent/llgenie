# Verifying a posted comment / issue body actually landed

`gh issue comment <n> -R <owner>/<repo> --body-file …` and `gh pr comment <n> …` print
the comment URL on success (`…/issues/<n>#issuecomment-<id>`). That URL — and the id
in it — IS proof the write succeeded; capture the id and use it (e.g. as the
`--verdict-ref … comment=<id>` for the acceptance write-back). Do not re-post because a
subsequent listing looked empty.

## The read-back quirk (verify, don't assume failure)

In this environment, listing comments through `gh api` with `--jq` can return **empty**
for comments that exist:

```bash
gh api repos/<owner>/<repo>/issues/<n>/comments --jq '.[] | select(.body|test("…"))'
# -> empty output, but the comment IS there (the post URL proved it)
gh api repos/<owner>/<repo>/issues/<n> --jq '.body'   # also can return empty
```

An empty listing is NOT evidence the post failed. Confirm with one of these instead:

1. **Issue/PR body** — use `gh issue view`, never the raw `gh api … --jq .body`:
   ```bash
   gh issue view <n> -R <owner>/<repo> --json body --jq '.body'
   ```
2. **A specific posted comment** — fetch the single-comment endpoint directly with the
   gh token via Python `urllib` (reliable where the `--jq` listing is not):
   ```python
   import subprocess, urllib.request, json
   tok = subprocess.run(["gh","auth","token"],capture_output=True,text=True).stdout.strip()
   cid = 1234567890
   req = urllib.request.Request(
       f"https://api.github.com/repos/<owner>/<repo>/issues/comments/{cid}",
       headers={"Authorization": f"token {tok}", "Accept": "application/vnd.github+json"})
   d = json.load(urllib.request.urlopen(req, timeout=20))
   print(d["issue_url"].split("/")[-1], d["body"].splitlines()[0])  # issue number + first line
   ```

Rule: a successful post prints a URL/id (that is the external-write confirmation); an
empty `gh api … --jq` listing afterwards is a listing quirk, not a missing comment —
re-verify through the single-comment endpoint or `gh issue view` before concluding
anything or re-posting.

## Verifying a PR *review* submission (the verdict, not a comment)

`gh pr review` writes to a different endpoint than a comment: `…/pulls/<n>/reviews`. Read
it back and assert the review is bound to the head you measured at — a review whose
`commit_id` is an older sha files the verdict against code that is no longer the branch:

```bash
gh api repos/<o>/<r>/pulls/<n>/reviews \
  --jq '[.[] | {id,state,commit_id,submitted_at,user:.user.login}]'
```

A single element whose `commit_id` equals the 40-hex head you reviewed is the proof. If a
second `COMMENTED` review already exists, you must have posted twice — do not post a third
time to "clean up"; report the duplicate id and leave review submissions alone (they cannot
be deleted via the API).

### jq pitfall: `.name()` is not jq

`--jq '[.review() | .[] | …]'` fails with `unexpected token "("` — jq has no method-call
syntax on API responses. The payload is already an array, so iterate the top level:
`--jq '[.[] | {id,state}]'`. A jq parse error is never evidence the read returned nothing;
fix the filter and re-read.
