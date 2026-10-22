# Resolve a finished fork run back to its PR

## Why

`auto-merge.yml` is a `workflow_run` workflow: GitHub hands it a **run id**, not a PR number, so the run
must be mapped back to its pull request before anything can be merged. On run `39735179724` (CI run
`39732261968`, PR #506, head `andyholst:fix/rebase-gate-mount`) that mapping destroyed the whole gate:

```
gh: Not Found (HTTP 404)
resolved PR #{
  "message": "Not Found",
  "documentation_url": "https://docs.github.com/rest",
  "status": "404"
} for run 39732261968 (head andyholst:fix/rebase-gate-mount)
##[error]Unable to process file command 'output' successfully.
##[error]Invalid format '  "message": "Not Found",'
```

The step was:

```bash
number=$(gh api "repos/$REPO/actions/runs/$RUN_ID/pull_requests" --jq '.[0].number // empty' || true)
if [ -z "$number" ]; then
  number=$(gh pr list --repo "$REPO" --search "head:$HEAD_BRANCH" --state open ...)
fi
echo "number=$number" >> "$GITHUB_OUTPUT"
```

Three defects in one snippet:

1. A fork `pull_request` run 404s on the runs endpoint, and `gh api` prints the error **body to stdout**.
   `|| true` discards the exit status, not the output, so `number` is the JSON blob.
2. The `[ -z "$number" ]` guard therefore never fires and the fork fallback added by #504 is **unreachable**
   for exactly the case it was written for.
3. That multi-line blob is appended to `$GITHUB_OUTPUT`, which GitHub refuses (`Invalid format`), so the
   step fails and `make auto-merge` never runs. The PR stays open and **no deferral comment is posted**,
   because `scripts/auto_merge.py` was never invoked — the silent stuck-PR mode AGENTS.md forbids.

Every agent PR is pushed to the fork, so every agent PR is affected; it only surfaces on the first green
one, which is why the four earlier runs were `skipped`.

## What Changes

- **`scripts/resolve_run_pr.py`** (new) — the resolution as a real, tested unit: the run object first, the
  head-branch search second, and a value counts only when it is digits, so a 404 body, an error line or an
  empty answer is "no answer". Nothing resolving exits non-zero naming the run and the head. The number is
  written as the single line `number=<n>` to `$GITHUB_OUTPUT`, or printed when that is unset.
- **`Makefile`** — `make auto-merge-resolve REPO= RUN_ID= HEAD_OWNER= HEAD_BRANCH=` is the one code path,
  added to `.PHONY` (AGENTS.md: a workflow runs make targets, so CI and the host run the same command).
- **`.github/workflows/auto-merge.yml`** — the inline shell step is replaced by that target, so the logic
  can never drift from the tested code.
- **`tests/test_resolve_run_pr.py`** (new, `make test-unit`) — the real resolver against a real fake `gh`
  binary on disk: the measured 404 falls through to the fork head, the run object is used when it answers,
  the search is scoped to the head owner, nothing resolving is loud, and `$GITHUB_OUTPUT` holds exactly
  one `number=` line. The workflow text is asserted to call the target and shell out to `gh` no more.

## Impact

- A green fork PR is merged by CI instead of dying in the resolution step.
- A green PR that genuinely cannot be resolved now fails **loudly** (and, once resolved, gets the deferral
  comment `scripts/auto_merge.py` writes) instead of vanishing.
