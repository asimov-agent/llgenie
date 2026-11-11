# Fabricated run ids and owner-merge auto-close

Two ways a lane's "verified" close proof can be false even when the lane is honest about not
having closed/merged anything.

## 1. A cited run id is a claim until `gh run view <id>` proves it exists

A lane reported a hf-live "SUCCESS run 41558411804 at the merged head". That id **404'd on
both the canonical repo and the producer fork** (`gh run view <id>` → `HTTP 404: Not Found`),
while the real `ci-hf-live` run at the same head was still `in_progress`. Find the real run by
listing and filtering on the head:

```bash
gh run list --limit 15 --json databaseId,status,conclusion,workflowName,headSha \
  --jq '.[]|select(.headSha|startswith("<merged-head>"))|{databaseId,status,conclusion,workflowName}'
```

Rules:
- `gh run view <cited-id>` before repeating any run id. 404 = the run does not exist and the
  "verified green" is fabricated — say so, do not propagate it onto the board.
- A run id that does not resolve is worse than no evidence: it reads as proof to the next reader.
- When a lane re-sends the same claim verbatim with the same unresolvable id, that is a re-quote,
  not new evidence — one sustained correction, not another verification loop.

## 2. Issue auto-closed by `closes #N` in the merge body ≠ condition-met close

GitHub closes an issue the instant a PR whose body contains `closes #N` is merged. So an issue
reading `state_reason=completed` closed in the **same second** as a merge is the **owner-merge
auto-close artifact**, not proof the issue's agreed close-condition ran.

Worked example: #1634 auto-closed 2s after the owner merged #1636 (squash body ended
`closes #1634`), while the agreed close-condition (hf-live re-green at the merged head) had not
yet executed. The closeness was the owner's act — legitimate, the owner merged — but
*evidentially* unproven.

Rules:
- Identify an auto-close: `state_reason=completed`, `closed_at` within ~seconds of the merge, and
  `closes #N` present in `git log -1 --format=%B <merge-sha>` or the PR body.
- **Never reopen a completed issue** — the close is the owner's/merge artifact, and reopening a
  merged PR's issue fights `main`'s own state.
- Verify the actual close-condition run independently. If it reds at the merge tip, file a NEW
  issue naming the merge commit sha + the real run id (red-on-main-after-merge class) and route
  it to the owning lane; do not reopen #N.
- Report the evidence plainly: "closed by owner merge `closes #N`, condition run still in_progress
  at head <sha>, not yet proven" — never "condition met" on the strength of an auto-close alone.
