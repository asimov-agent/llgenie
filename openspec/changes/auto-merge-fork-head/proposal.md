# The auto-merge job accepts the owner's fork as a PR head

## Why

`auto-merge` shipped requiring a same-repository head:

```yaml
github.event.pull_request.head.repo.full_name == github.repository
```

That condition was copied from `trending-local-llms`, whose bots push branches **inside** the repo. llgenie
is the opposite: every PR this repository opens from an agent is pushed to `andyholst/llgenie` and opened
cross-repository (AGENTS.md; the clone's remotes are inverted — `origin` is the upstream, `fork` is the
owner's fork). So the job skipped exactly the PRs it was built for.

Measured on PR [#481](https://github.com/asimov-agent/llgenie/pull/481) after #483 merged:

```
$ gh pr view 481 --json headRepository,mergeable,mergeStateStatus
head=andyholst/llgenie   mergeable=MERGEABLE   mergeStateStatus=BLOCKED
$ gh run list --branch feat/architecture-bot-pr-retry
39622924064  2026-10-21T15:07:57Z  pull_request    # 68 minutes BEFORE #483 merged
```

Two reasons it never merged: the fork head excluded it, and no run has been created since the job landed
(a `pull_request` run only starts on a push to the branch). `BLOCKED` is GitHub reporting stale
merge-commit checks after `main` advanced.

A fork head also cannot have its branch deleted from the base repository: `gh pr merge --delete-branch`
would fail **after** a successful merge, turning the run red for no reason.

## What Changes

- **`.github/workflows/ci.yml`** — the head condition accepts the base repo **or** the owner's fork
  (`github.event.pull_request.head.repo.owner.login == 'andyholst'`, the account the merge PAT belongs to).
  Any other fork stays manual, and every other guard is unchanged (non-draft, not `main`, every needed job
  `success`, the push-only job not in `needs:`).
- **`scripts/auto_merge.py`** — the same `gh pr view` that reads the merge state now also reads
  `headRepository`; `--delete-branch` is passed only when the head repository **is** the base repository, so
  a fork merge succeeds and the fork branch is kept. No extra workflow plumbing: the decision and the argv
  stay in one place.
- **`tests/test_auto_merge.py`** — a cross-repository head merges without `--delete-branch`, a same-repo head
  still deletes its branch, and the workflow's condition allows exactly one fork owner (and no wildcard).
- **`AGENTS.md`, `README.md`, the spec** — state the trusted-fork rule and that its branch is kept.

## Impact

- A green, conflict-free PR from `andyholst/llgenie` is merged by CI like a same-repo one, which is the
  normal case here.
- A fork merge leaves the branch in the fork (the base token cannot delete it) — printed in the log, not an
  error.
- Any other fork, a draft, a conflicted/stale/blocked PR, a moved head and `do-not-merge` still defer.
