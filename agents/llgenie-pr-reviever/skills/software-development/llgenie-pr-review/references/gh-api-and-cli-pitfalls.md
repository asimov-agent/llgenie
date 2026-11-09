# `gh` CLI vs REST pitfalls while gathering evidence

The CLI (`gh pr view --json`, `gh run list --json`) and the REST API (`gh api`) speak DIFFERENT field
names for the same object. Mixing them returns `null`, never an error, and a `null` reads as "no such
run" and invites a bogus re-dispatch.

## Field-name divergence

- REST run object: `id`, `head_sha`. CLI `gh run list --json`: `databaseId`, `headSha`. So
  `gh api repos/<o>/<r>/actions/runs/<id> --jq '{databaseId,conclusion}'` prints
  `{"databaseId":null,…}` on a perfectly live run. Read the run you queried with `id`/`head_sha`;
  use `databaseId`/`headSha` only on `gh run list --json` output.
- `commits/<sha>/check-runs` returns an OBJECT holding a `check_runs` array — iterate `.check_runs[]`,
  never `.[]` (which errors `cannot iterate over: number` and hides the real job states).
- `gh pr view --json` has **no `merged` boolean**: ask for `state`, and `mergedAt`/`mergedBy`/
  `mergeCommit` are the merge facts. `--json merged` errors `Unknown JSON field` and prints the whole
  available-fields list, which reads like a broken command rather than a wrong field.
- `gh issue view --json` has no `timelineItems` (nor `merged`). For a close-event timestamp use
  `--json closedAt,closedByPullRequestsReferences`; for acceptance-criteria state read `.body` and grep
  the checkboxes. **`gh api … --jq .body` emits raw text, not JSON**, so it never round-trips through
  `json.loads` — treat every such read as a string.

## Freshness and liveness

- `gh run list --commit <sha>` lags a fresh push; the API does not. Minutes after a push it can report
  no runs for a sha that already has three (reads as "CI never triggered"). Ask the API:
  ```bash
  gh api "repos/<o>/<r>/actions/runs?branch=<ref>&per_page=10" \
    --jq '.workflow_runs[] | select(.head_sha=="<sha>") | "\(.id) \(.status)/\(.conclusion) | \(.name)"'
  ```
  A superseded head shows its old runs as `completed/cancelled` after a force-push — `no verdict` at
  the OLD sha; filter on the NEW `head_sha` before saying anything about the branch.
- A fork PR head is not a commit in the base repo's object DB: `commits/<sha>/check-runs` answers
  `422 No commit found for SHA` and `actions/runs?head_sha=<sha>` answers `total_count: 0`, and both
  read as "no runs" when the PR is fully covered. `gh pr checks <n> --repo <base>` is the primary read
  because it resolves a PR head wherever the object lives. For the object itself:
  `git fetch origin refs/pull/<n>/head:refs/remotes/pr/<n>` (a bare fork-sha fetch may error
  `upload-pack: not our ref`). Judge only the rows `gh pr checks` returns for the `headRefOid`
  `gh pr view` names — a prior head's `CANCELLED` leg describes the old sha.
- **`mergeable_state` is a background computation, not a check result.** Minutes after a push it can
  read `blocked` (the stale pre-recompute frame) and then `unknown` with `mergeable: null` while GitHub
  recomputes. Neither is a red: a `blocked` that survives several reads with **zero failing check-runs,
  no labels, and base == live main** is a stale/recomputing field, not a hold. Prove the absence of a
  real hold before reporting one: `gh api repos/<o>/<r>/rulesets` (a `main` ruleset carrying only
  `deletion`/`non_fast_forward` requires no checks) plus
  `commits/<head>/check-runs --jq '[.check_runs[]|select(.conclusion!="success")]'` returning empty.
  Report the measured facts ("check-runs 16/16 SUCCESS, state unknown = GitHub recompute") and poll a
  few times; never convert a recompute lag into a do-not-merge or a "still blocked" verdict.

## Job logs

`gh api …/actions/jobs/<id>/logs` reads EMPTY through `--jq .` and errors on escape sequences without
`--allow-escape-sequences` — redirect it raw, never pipe it:

```bash
gh api repos/<o>/<r>/actions/runs/<run>/jobs --jq '.jobs[]|{id,name,conclusion}'   # enumerate first
gh api repos/<o>/<r>/actions/jobs/<jobid>/logs --allow-escape-sequences > /tmp/job.log
```

`gh run view <run> --log-failed` picks the FIRST failing job in the run and can return
`log not found: <a different job id>` when the job carrying your finding is not that one. Grep the
saved log for `AssertionError|FAILED` lines rather than paging 60 KB.

## Shell and cwd traps

- Build a comment body in a file and read the published body back, not the post's exit code. A
  `gh api … --jq "…\"$var\"…"` nested in a double-quoted shell string collapses silently (empty field,
  exit 0). Quote the heredoc delimiter (`<<'EOF'`): an unquoted body expands backticked spans and
  `$var` as command substitution. Repair a blank/wrong body with `PATCH /repos/<o>/<r>/issues/comments/<id>`
  and re-read it. Full mechanics, including the `-F` vs `-f` file-body rule and the REST review
  create/update endpoints: `references/posting-review-record.md`.
- Post the comment as its OWN tool call and confirm its id landed. A post batched with read-only calls
  can be vetoed by a mutation guard and never execute, with no error on the post itself — read the id
  list back and confirm the new id is present before reporting it posted.
- Removing a worktree the terminal is cwd'd into breaks every later call: the persisted shell cwd
  points at a deleted dir and commands fail `cd: … No such file or directory` (reported as exit 126).
  `cd` back to the main clone, or pass `workdir=<main clone>` on the removing call and on every call
  after it.

## Docs gates that red on YOUR new files

- A newly added text/markdown file must end with a trailing newline or `lint_linefeeds` reds the docs
  gate. Check with `tail -c1 <file> | od -An -c`; a last byte that is not `\n` is the violation. Fix is
  appending the newline, not editing the lint.
- A peer's "my local lint is clean on the same tree" does not contradict a CI red: the local tree is
  usually at the base, where the diff's new files do not exist. The gate runs against the branch head,
  sees the new files, and reds on them. Read the job log to name the exact file.
