# The merge runs where the secrets are

## Why

PR #481's run was **green** and its `auto-merge` job **succeeded** — and the PR stayed open. The job's log:

```
env:
  HF_TOKEN:
  GITHUB_TOKEN: ***
  GH_TOKEN:                      <-- EMPTY: secrets.BUMP_TOKEN resolved to nothing
  PR: 481
[auto-merge] PR #481: {"mergeable": "MERGEABLE", "mergeStateStatus": "BLOCKED", …}
[auto-merge] PR #481 deferred to a human: mergeStateStatus is BLOCKED (…)
```

`secrets.BUMP_TOKEN` is used in 32 places and the bots push with it, so the secret exists. It is empty **here**
because #481 is a **fork PR** and the job lived in `ci.yml`, which runs on `pull_request`: GitHub withholds
repository secrets from a `pull_request` run coming from a fork. (`HF_TOKEN` is empty for the same reason;
`GITHUB_TOKEN` is present but read-only.) Every agent PR in this repository is pushed to `andyholst/llgenie`,
so **every** one of them had a merge job that could never merge.

`trending-local-llms` never hit this because its bots push branches inside the repo.

## What Changes

- **New `.github/workflows/auto-merge.yml`**, triggered by `workflow_run: workflows: ["CI"], types: [completed]`.
  A `workflow_run` workflow executes in the BASE repository with the BASE repository's secrets, so the owner
  PAT exists. It acts only when `event == 'pull_request'` and `conclusion == 'success'`, resolves the PR from
  the finished run (`gh api repos/{repo}/actions/runs/{id}/pull_requests`, falling back to
  `gh pr list --head owner:branch`), and calls the same `make auto-merge`. One implementation, no second
  merge path.
- **It checks out the BASE branch**, never the PR head: the job holds a write token, so it runs trusted code.
- **The `auto-merge` job is deleted from `ci.yml`**, with a comment saying where it went and why; the skip
  guard's scenario-scoped exception in `tests/test_ci_images.py` goes with it (no job needs it now).
- **A missing token is loud.** The workflow's first step fails (exit 2) when `secrets.BUMP_TOKEN` is empty,
  and `scripts/auto_merge.py::_require_token` exits 2 when neither `GH_TOKEN` nor `GITHUB_TOKEN` is set: a run
  that cannot merge must never look like one that chose not to.
- **The trust boundary moves into the decision.** A `workflow_run` fires for any fork, so `decide()` now
  refuses a head whose repository is neither this repo nor `andyholst/llgenie`
  (`TRUSTED_HEAD_OWNERS`) instead of relying on a job `if:`.

## Impact

- A green fork PR merges with no human click, and its job log shows `GH_TOKEN: ***` instead of empty.
- A missing credential reports red, naming itself, instead of reporting success.
- A stranger's fork is never merged by this repo's bot.
