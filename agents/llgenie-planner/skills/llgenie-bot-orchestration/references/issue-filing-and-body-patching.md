# Filing, editing and verifying issue bodies

Mechanics for the two writes a planner makes constantly — creating a refined issue and commenting on
one — plus the read-back that proves each landed. Every step here exists because the naive version
produced a silent wrong result.

## 1. Never batch a write that CREATES a row

Two `gh issue create` calls issued in one parallel tool block both fire, and you get two identical
issues. The same holds for comments: two parallel `gh api .../issues/<n>/comments -f body="$(cat /tmp/body.md)"`
commands post the SAME body twice, ~1 second apart, and the second is invisible in the first command's
exit code. Post a comment ONCE, capture the returned `.id`, and only then read it back (§5). If a duplicate
lands anyway: **GitHub's REST API cannot delete an issue comment** — `PATCH` the later one to a one-line
pointer (`_Duplicate of <id> (posted 1s later by the same pass). See that comment._`) so exactly one
full-body comment remains, then verify the count with `[.[]|select(.body|startswith(<header>))]`. Create one, read its number back, then create the next. If duplicates exist anyway: keep
one, close the other with a comment naming the survivor, and fix the survivor's body so it says
`closes #<survivor>` — a draft placeholder number left in the body points the PR at the wrong issue
and reds `check-pr-closing` later.

## 2. Never `sed -i` a multi-line markdown body

Backticks, `$`, parentheses and `**` in a six-section issue body defeat sed escaping. The
substitution silently matches nothing, so you PATCH a stale body and believe it changed. Edit the
draft with the patch tool, then PATCH via the API and read the body back:

```bash
gh api repos/{owner}/{repo}/issues/<n> -X PATCH -f body=@/tmp/body.md --jq .number
gh issue view <n> --json body --jq .body | grep -c '<expected-token>'
```

## 3. Verify with a marker that survives markdown rendering

A regex check against rendered prose is a false-negative machine: `**Trigger divergence**` renders
without matching `test("\\*\\*Trigger divergence\\*\\*")`, backticks vanish, `[x]` lists re-render.
Assert on distinctive plain words (`test("Trigger divergence")`) or compare the raw `.body`. Never
record "verified" on a check whose pattern you have not confirmed against the raw body — a
false-fail becomes a false ledger entry, and the ledger is what the next pass trusts.

## 4. Patch only the live directives, then count the rest

A body may legitimately quote a stale sha as history (the merge sha of the PR it was filed after).
Replace only the branch-from instructions, and prove the delta with counts rather than eyeballing:

```bash
gh issue view <n> --json body --jq .body | grep -c '<stale-sha>'   # expect the historical count only
gh issue view <n> --json body --jq .body | grep -c '<new-sha>'     # expect the directive count
```

## 5. Prove a comment landed on the issue you meant

**Listing shape:** `GET /repos/{owner}/{repo}/issues/<n>/comments` returns a **bare JSON array**, not
`{comments:[...]}`. A query written `[.comments[]|...]` fails with `expected an object but got: array` and
reads as "zero matching comments" if you swallow the error — you then conclude your post did not land (or
that no duplicate exists) when it did. Use `[.[]|...]` for the list endpoint and `[.comments[]|...]` only
for a wrapped response.

```bash
gh api repos/{owner}/{repo}/issues/comments/<id> --jq \
  '{id,issue:(.issue_url|split("/")[-1]),ok:(.body|test("dispatch: \\\\#<n>"))}'
```

The create returns an id; the read-back returns the issue number and a content marker. Report the
id in your pass report, never "posted the comment".

## 6. Pre-measure the baseline you dispatch against

When a dispatched lane reports it will "confirm the baseline", and you already measured those
facts, post the numbers to the thread (with the comment id) so it does not spend a cycle re-deriving
them. In the same comment, name which of its candidate fixes sidesteps a parked gate — e.g.
re-pointing a trigger onto an enabled workflow instead of re-enabling a disabled one (which needs an
owner ruling). That is the difference between a lane that starts fixing and a lane that stalls on a
dependency it never needed.
