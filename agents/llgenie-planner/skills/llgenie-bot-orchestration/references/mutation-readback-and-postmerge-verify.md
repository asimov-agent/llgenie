# Verifying your own mutations, and post-merge truth

A planner's write to the board is a claim until a second read proves it. These are the read-back and
post-merge checks, plus the quoting trap that silently corrupts comment bodies.

## 1. Read back every mutation you make

- **Comment posted?** `gh api repos/<o>/<r>/issues/<n>/comments --jq '[.[]|select(.id==<id>)]|length'` → `1`.
  Assert a distinctive substring of the intended body too (`select(.id==<id>)|(.body|contains("<marker>"))`),
  so a post that landed with the wrong text does not pass.
- **Issue closed?** `gh issue view <n> --json state,stateReason` → `CLOSED` + `COMPLETED` (or `NOT_PLANNED`).
  `CLOSED` with no/odd reason means something else closed it.
- **Label applied?** `gh issue view <n> --json labels --jq '[.labels[].name]|join(",")'` and quote the set.
- Do the verification in the same turn as the mutation. If a pass genuinely has no mutation to make,
  say "nothing could move" with the measurement that proves it — never dress a non-mutation up as verified work.

## 2. Post comment bodies from a JSON file, never inline

Inline bodies mangle two ways: `gh api -f body="$(cat file)"`/heredocs colliding with quotes, and jq
`\(...)` interpolation inside a shell double-quoted string (the shell eats the escapes → a jq expression parse error).

Reliable path:

```bash
python3 -c 'import json;open("/tmp/p.json","w").write(json.dumps({"body":open("BODY.md").read()}))'
gh api -X POST repos/<o>/<r>/issues/<n>/comments --input /tmp/p.json --jq '.id'
```

Keep every `--jq` expression in single quotes; never assemble a jq program by string concatenation in shell.

## 3. Post-merge truth: `state: MERGED` is the verdict

- `gh pr view <n> --json mergeStateStatus,mergeable,state` can return `mergeStateStatus: UNKNOWN` and
  `mergeable: UNKNOWN` on a PR that has just merged (with `reviewDecision` still `APPROVED`).
  `state: MERGED` + a non-null `mergedAt` is authoritative; `UNKNOWN` on a merged PR is a field flap, not a defect.
- **When `mergedAt`/`mergedBy`/`mergeCommit` read `null` in `gh pr view --json`,** the PR merged and its branch
  was deleted — the pull-request object drops the merge fields. Do not report "merge identity unknown": read the
  timeline, which keeps it: `gh api repos/<o>/<r>/issues/<n>/timeline --jq '[.[]|select(.event=="merged")|{actor:.actor.login,commit_id}]'`.
  Cross-check `autoMergeRequest` on the PR (null = not armed) before concluding a lane self-merged.
- Confirm it landed on the intended base: read `baseRefName` (a stacked PR does not land on `main`), then
  `git fetch origin main`, `git merge-base --is-ancestor <mergeCommit.oid> origin/main`, and `git log origin/main -1`.
  The new `main` head should be the squash commit.
- **Approval genuineness**: read `/pulls/<n>/reviews` and quote `author_association` (`OWNER` vs
  `MEMBER`/`CONTRIBUTOR`/`NONE`) and `submitted_at`. A merge seconds after an approve is normal when the
  owner approved personally — the shared-token self-approval shape is a non-OWNER association, not a fast clock.
  Do not escalate an `OWNER` approval as an incident.
- **Head green ≠ main green.** The PR's own checks passing at the head do not prove the merge tip is green.
  The merge-tip re-run (`gh run list --branch main` filtered to the new head sha) is a separate gate; wait for it
  to conclude before declaring main green, and say "pending" while it runs.

## 4. Folding duplicates onto a consolidation home

- When several issues share one root, post the fold **on the home issue**: name each absorbed issue and its state
  (closed-as-duplicate, or open + `duplicate`-labelled and owner-parked), state the single root and the scope,
  and require the eventual PR body to reference the absorbed ids so the fold survives to merge.
- Applying a `duplicate` label is planner board state and is fine out of band; the close-vs-rescope decision on an
  owner-parked issue stays with the owner.
