# Each bot write runs with the token that can perform it

## Why

`issue-bot.yml`'s PR step ran the whole `make issue-bot-open-pr` under one token:

```yaml
env:
  GH_TOKEN: ${{ secrets.BUMP_TOKEN }}
```

That step makes **two different writes**: it posts the issue comment that marks the issue as claimed,
and it creates the pull request. The PAT can open a PR (which is why it is used — a PR opened with
`github.token` does not trigger CI, issue #420) but it carries no Issues write. Run
[39513850754](https://github.com/asimov-agent/llgenie/actions/runs/39513850754):

```
[issue-implementer] gh issue comment 407 --repo asimov-agent/llgenie --body <!-- bot-done: implementer … pr-open -->
Implemented on `agent/issue-407-…`: https://github.com/asimov-agent/llgenie/pull/424. …
failed (1): GraphQL: Resource not accessible by personal access token (addComment)
make: *** [Makefile:380: issue-bot-open-pr] Error 1
```

PR #424 already existed when that happened. The job went red *after* its side effect, so the run looked
like "no PR" while the PR was open, and the `pr-open` marker that tells every other bot the issue is
occupied was never posted — a second run could pick the same issue and open a second PR (issue #430).

The step that *can* comment — the outcome report — already used `${{ github.token }}` and succeeded, so
the capability existed and was simply not given to the write that needed it.

## What Changes

- **`scripts/issue_implementer.py`** — `_gh()` takes a per-call `token`, which it sets as `GH_TOKEN`
  for that child process only (the leg's own environment is never mutated). `pr_token()` reads
  `PR_TOKEN` (the PAT) and falls back to the leg's token. `open_pr()` now posts the claim comment
  **first** with the issues-scoped token, then creates the PR with the PAT, then posts the `pr-open`
  marker with the issues-scoped token.
- **`.github/workflows/issue-bot.yml`** — the PR step carries both: `GH_TOKEN: ${{ github.token }}` for
  the comments and `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}` for `pr create`.
- **`tests/test_bot_pr_tokens.py` (new)** — a **real** fake `gh` binary records the argv *and the
  `GH_TOKEN` it actually received*: the comment and the marker get the job token, `pr create` gets the
  PAT, in that order; a denied comment fails **before** any PR exists; an unset `PR_TOKEN` falls back to
  the leg's token; and the workflow hands the step both.
- **`README.md` + `agent-wiki/`** — which write uses which token, and why.

## Impact

- A token that cannot comment can no longer leave a PR behind: the comment that can be denied runs
  first, so a red run means nothing was half-done, and the log names the denied write.
- The issue is claimed the moment the PR is opened, so a second bot run cannot duplicate it.
- The PR still triggers CI, because `pr create` still uses the PAT.

## Out of scope

- #426, #427, #428, #429 — the stub-PR defects filed from the same run; each is its own change.
