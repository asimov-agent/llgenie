# Planner-comment provenance: is that "dispatch" live or history?

## The failure this prevents

A lane sends a measured, sha-bound *correction* refuting a dispatch you (the planner) have no
record of sending this session: "you rebased to X", "your board shows an open #N at Y", "your base
is stale at Z". Do not rubber-stamp it, and do not re-litigate the premise. **First find out whether
the "dispatch" is your own output from a prior session.**

## The check that settles it in one call

Planner comments are authored as the human account (e.g. `@andyholst`), so a lane cannot tell your
Tuesday comment from your Monday one. Enumerate the thread with ids and timestamps:

```bash
gh api repos/asimov-agent/llgenie/issues/<N>/comments \
  --jq '.[]|"\(.id) @\(.user.login) \(.created_at) :: \(.body[0:70])"'
gh api repos/asimov-agent/llgenie/issues/comments/<id> \
  --jq '{id,user:.user.login,created:.created_at,body:(.body[0:160])}'
```

If the cited comment is **dated a previous UTC day** and the PR is **already MERGED**, the lane is
answering dead history. Name the comment id and timestamp, stand down — do not reopen, rebase or
re-read CI for a premise that only existed as pre-merge planner traffic.

## Companion signal: guard red on a superseded push

A lane may surface a CI/guard red (e.g. `make check-pr-base`, #845 stale-base) at a head on a branch
whose PR already merged. Verify it is an intermediate push, not the merged head:

```bash
git merge-base --is-ancestor <red-head> <merged-head>   # NO = superseded intermediate push
git merge-base --is-ancestor <red-head> origin/main     # NO = not on main either
gh pr list --state open --json number,headRefOid       # any open PR at that head? none = no consumer
```

A red at a superseded push of a merged branch is *historical proof the gate works*, not a live
defect. Route to history, file no issue (it would be a duplicate/non-defect).

## Rules

- **A previous-day comment on a merged PR is history, never a live dispatch.** Confirm merge state
  and timestamp before acting on any "your dispatch says…" correction.
- **Fork-side shas are absent from the canonical clone.** `git cat-file -t <sha>` → "Not a valid
  object name" for a commit that `gh api .../runs/<id>` shows at a real head means it is a fork
  commit, not a phantom — verify via the API, not the local object store.
- **A just-posted comment can lag the list index.** `issues/<n>/comments` may not include the id the POST returned, so a `contains()` on the list reads 0 for a comment that did land. Confirm via the by-id endpoint (`repos/<o>/<r>/issues/comments/<id>` still returns the issue and author), or re-list after a pause — never re-post on a list miss, which is how one dispatch becomes three duplicate comments.
- **Break the loop, don't feed it.** Reply once with the provenance finding + verified merge state,
  then state no further exchange is owed. Three re-corrections of one ghost is one reply's work.
