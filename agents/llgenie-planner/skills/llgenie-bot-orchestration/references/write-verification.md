# Verify what you wrote, not that the write succeeded

A successful API call is not a landed document. After every programmatic write, read the artifact back for
**shape and length**, never the exit code.

## Failure modes

- **`gh issue create`/`gh pr create` with a nonexistent label fails ATOMICALLY — nothing is created.** A bad
  `--label component:engine` exits non-zero naming only the missing label ("could not add label: 'component:engine'
  not found") and **the whole create is aborted**, so the issue never exists. The trap is the next step: a search for
  your title returns nothing and you conclude the create "silently failed" and re-create — but the real defect is the
  label, not the create. **Validate label names before writing: `gh label list --repo <o>/<r> --limit 200
  --json name --jq '.[].name' | grep -iE '<class>'`** — engine issues use `component:container`, not a
  `component:engine` that was never created. Then create, and verify the issue really landed (see the read-back rule).
- **A freshly created issue can 404 on the immediate read — retry once, never re-create.** `gh issue create` returns
  the new URL/`#<n>`, but `gh api repos/<o>/<r>/issues/<n>` run in the same breath can return `Not Found (HTTP 404)`
  because the API has not yet propagated the new object. Do NOT read the 404 as "the create failed" and POST again
  (that makes a duplicate): `sleep 3` and re-read the same `<n>`. The 404-then-success is propagation lag; the receipt
  that matters is the later read returning `{number, state, labels, body}` — grade the body on THAT read, not on the
  in-flight one.
- **`gh issue create --body -` stores a literal `-`.** stdin is consumed only by `--body-file -` (or `-F body=@file`
  on `gh api`). The issue is created, the command exits 0, and the body is one character.
- **A comment posted while another lane edits the same body can be overwritten** by their next PATCH.
- **NEVER index the comment list to prove a post landed — `.[0]` and `.[-1]` are both unreliable.** The
  issue-comment API returns **oldest-first**, so `.[-1]` pulls the newest and `.[0]` the oldest — and on a busy
  PR the oldest entry is an `asimov-agent` auto-merge stub (`<!-- auto-merge: deferred … -->`), so a `.[0]`
  read-back of your fresh post silently grades that stale stub instead of your comment. `.[-1]` is equally
  fragile once a lane replies after you. Trust the **POST response**'s `id` and read that exact id back:
  `gh api repos/<o>/<r>/issues/comments/<id> --jq '{id,at:.created_at[11:19],login:.user.login,body:.body[0:80]}'`.
  Only an `id`+`created_at` match proves the post exists; an index lookup returning a different author or a
  pre-write timestamp is proof it did NOT read your comment.
- **Capture the id from the POST command's OWN stdout — do not re-derive it by scanning the list.** `gh issue
  comment … --body-file <f>` / `gh pr comment` print the created URL (`…/issues/<n>#issuecomment-<ID>`); read `<ID>`
  off that line and fetch it directly. Re-deriving the id by listing and body-matching is the failure that bites
  hardest when the channel degrades: a `?per_page=10` comment fetch can return an OLD page (e.g. comments from days
  earlier) while the fresh post is absent from that page, so a scan finds `0` matches and reads as "NOT LANDED —
  repost", which would double-post a comment already on the wire. Absence from a list page is not absence from the
  thread; the POST's printed id is the strong receipt, and a direct `…/issues/comments/<ID>` fetch returning
  `{id, created_at, login}` is the proof. Fetch by id; never report "not landed" off a list scan.
- **When a LANE reports it could not confirm its own landed comment, verify it thread-side — degraded display
  does not mean the POST failed, and neither does "posted" mean it landed.** A lane whose stdout renders garbled
  (command execution fine, display corrupt) will say "the record is posted but I could not read back the id." Do
  not accept that at face value in either direction: execution success ≠ landed write, and a corrupt *display* is
  not proof the POST failed. Read the issue's comment list yourself with a **full pagination** and match on a body
  prefix:
  ```bash
  gh api repos/<o>/<r>/issues/<n>/comments --paginate \
    | python3 -c "import json,sys;d=json.load(sys.stdin);rs=d if isinstance(d,list) else d['comments'];\
print([(c['id'],c['created_at']) for c in rs if (c.get('body') or '').startswith('<first 40 chars>')])"
  ```
  Unlike a single `?per_page=N` page, a `--paginate` scan that matches nothing **is** proof of absence (the
  thread is fully walked). When the body is absent from the full thread, the write genuinely did not land → tell
  the lane to re-post and confirm the new id. When it IS present, quote the id and timestamp back so the lane
  stops doubting a write that landed. In both cases the durable record's *content* (in the lane's scratch file) can
  be trusted while its *landing* cannot — verify landing separately.

## Never re-POST to fix a read-back you did not like

A read-back that returns a stale entry, an empty list, or a guard nudge is **never** a licence to POST again.
Re-running the POST to "make sure it landed" is how one board note becomes five identical comments on a live
issue — each retry exit 0s, and the board now carries copies nobody will clean up.

- **Post at most once per turn, and only after the body is final.** If the verification command itself failed
  (bad jq, wrong index, truncated output), the defect is in the *reader*, not the write. Fix the reader and
  re-read the **id you already have**; do not write again.
- **Before any retry-shaped POST, check for an existing identical comment:**
  ```bash
  gh api repos/<o>/<r>/issues/<n>/comments --paginate \
    | python3 -c "import json,sys;d=json.load(sys.stdin);rs=d if isinstance(d,list) else d['comments'];\
print([c['id'] for c in rs if (c.get('body') or '').startswith('<first 40 chars of your body>')])"
  ```
  Match on a **body prefix**, not on a timestamp or an index — the list is oldest-first and lanes reply after you.
  Prefix-matching cannot catch a **reworded** re-post: the same board fact rephrased five ways slips past a
  prefix dedupe and still spams the issue. So the primary guard is the rule itself — one POST per fact per turn;
  when the guard nags, do a genuinely different mutation (a dispatch, a label PATCH, a DELETE), never a reworded
  restatement of the same fact.
- **A guard demanding "a mutation" is not a demand for another POST.** The mutation may be a DELETE, a label
  PATCH, a dispatch, or a read that changes what the board says. Repeating a write already on the wire is the
  one mutation that makes the board worse.
- **When the guard fires repeatedly on turns that DID mutate, do not fabricate — execute the consequence-chain
  duty the mutation created.** The static check can thrash for several passes against work that was genuinely
  landed and verified elsewhere in the turn. The way out is never a second, invented mutation to appease it; it
  is to find the duty that BECOMES DUE as a direct consequence of the change you already made and do THAT. A
  landed rebase invalidates a lane's watcher on the old head → re-aiming that watcher is the owed mutation; a
  merge closes an issue's premise → writing the post-merge record is the owed mutation. Reason forward from the
  change you landed, not backward from the guard's complaint. If a genuinely due consequence-duty does not exist,
  report "state unchanged since <sha>" and stop — fabricating to clear a static guard is the anti-pattern.
- **A literal-path body on a CREATE, not just a comment, is the same `-f`/`-F` tell.** `gh api -X POST .../issues
  -f body=@/tmp/x.md` creates an issue whose body IS `@/tmp/x.md` (a ~30-byte body), the create exits 0, and no
  error names the cause. The tell is a short body whose text equals the file path. Fix it with a `-X PATCH ...
  -F body=@/tmp/x.md` (capital `-F`), never by deleting and re-creating the issue (a re-create is a duplicate with
  a new number and a dead thread).
- **Never batch the SAME mutating POST across parallel tool calls in one turn.** Independent reads belong in one
  parallel block; a write does not. Issuing the same (or several variant-flag) `gh api …/comments -f …` calls as
  N entries of a single batched tool block runs ALL of them — the runtime executes every entry — so one intended
  comment becomes N. When a POST's shape is uncertain, run it as ONE call, read the id back, and only then decide
  whether a second (different) write is needed. Parallelism multiplies a bad flag into a spam burst instead of a
  single failure.
- **If duplicates did land, clean them up and say so plainly.** Keep the earliest, delete the rest, then verify
  the count is 1:
  ```bash
  gh api -X DELETE repos/<o>/<r>/issues/comments/<id> -i | grep -i ^HTTP   # expect 204
  ```
  Report the duplication in your own summary — an unreported duplicate comment reads to the next lane as
  disagreement or spam.

## Read it back

```bash
gh issue view <n> --repo <o>/<r> --json body \
  --jq '{len:(.body|length), sections:[.body|split("\n")[]|select(startswith("## "))]}'
gh api repos/<o>/<r>/issues/comments/<comment_id> --jq '{at:.created_at,len:(.body|length)}'
```

**`jq`'s `+` is type-strict — concatenating a string with a number throws `cannot add: string ("#") and number (1871)`.**
`--jq '"#"+.number'` and `"len="+len` both fail, and because the error arrives alongside a real HTTP success the
temptation is to read the call as failed. Coerce every non-string operand: `--jq '"#"+(.number|tostring)'`,
`--jq '"len="+(.body|length|tostring)'`. Prefer the array-free form `(.number|tostring)` over `[...]|join("")` — the
latter silently drops `null` fields and reports a shorter id string than the object actually has.

A six-section issue body reads ~2-9 KB; a comment reads ~1 KB. A body of length 1 is a missing document, and a
planner who reports "issue filed" on a 1-byte body has reported a title.

## Writing a multi-line body from a file

`gh api .../issues/<n>/comments -F body=@/tmp/x.md` is the reliable form for a long comment; it returns the
created object with its `id` and `created_at`, which is your verification receipt (see above). Keep the file in
scratch, not the repo.

**`-f` is NOT `-F`: `-f body=@/tmp/x.md` posts the four-character-ish literal string `@/tmp/x.md` as the body.**
`-f` takes a raw string value; only `-F` (force-file) treats a leading `@` as a filename. A batch that retried a
doomed `-f body=@file` posted N identical literal-path comments onto a live PR, each exit 0. The tell is a
comment whose entire body is `@/tmp/...` — that is proof of a malformed flag, not a landed dispatch. When that
happens: DELETE every literal (`gh api --method DELETE .../issues/comments/<id>` returns 204), keep the single
good-content comment, and re-list to confirm zero `@/tmp`-bodies remain before finishing.

**`gh api` does not accept curl's `-o`/`--output-designation`.** `--output`/`-o /dev/null -w '%{http_code}'` errors
with `unknown shorthand flag: 'o'`. To read the HTTP status of a DELETE, either append `-i | grep -i ^HTTP`
(expect `204`) or pipe through `--jq '.'` (exit 0 + empty body == deleted).
