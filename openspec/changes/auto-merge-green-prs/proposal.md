# llgenie merges a green, conflict-free PR itself

## Why

Every llgenie PR waits for a human to click merge even when the whole pipeline is green, the branch is a
fast-forward and the change is one bot's single objective. `AGENTS.md` ("Git workflow", rule 7) makes that
durable for the agent — "the agent NEVER merges … even when asked to merge, ship or push to main, the agent
stops at the open, reviewable PR" — so green work sits until someone is at the keyboard, and every bot that
produces a PR ends its run saying "awaiting review".

`trending-local-llms` closes that loop in CI, and the shape is worth copying exactly
(`.github/workflows/qa-validate.yml`, job `auto-merge`): it `needs:` the green jobs, restricts itself to a
non-draft same-repo `pull_request`, and then

```
gh pr merge "$PR_NUM" --repo "$REPO" --squash --delete-branch --match-head-commit "$HEAD_SHA"
make verify-closure PR="$PR_NUM" REPO="$REPO"
```

with the **owner PAT** — a merge made with `GITHUB_TOKEN` starts no workflows, so the post-merge run on
`main` would never happen — and it proves afterwards that the body's `closes #n` actually bound, so an
unbound keyword is a red run rather than an issue left open.

llgenie's CI is heavier (the pipeline runs on Linux and macOS, plus the engine-image matrix and the
published-image install stage), so the job belongs in `ci.yml`, `needs:` every PR-relevant job, and must
merge **only** a green *and* conflict-free PR: `mergeStateStatus == CLEAN`.

## What Changes

- **`.github/workflows/ci.yml`** — a new `auto-merge` job:
  - `needs: [guard, ci-images, linux, macos, engine-base, engine-matrix, engine-image, linux-published]`
    and `if: always() && !failure() && !cancelled()` (the push-only `engine-published-test` job is
    skipped on a PR and must not block it);
  - runs only for `github.event_name == 'pull_request'`, a non-draft PR, a **same-repo** head (a fork PR
    stays manual) and a head branch that is not `main`;
  - reads `gh pr view <n> --json state,isDraft,mergeable,mergeStateStatus,headRefOid,labels` and merges
    only when the PR is `OPEN`, `mergeable == MERGEABLE`, `mergeStateStatus == CLEAN` (that is what
    excludes `DIRTY` conflicts, `BEHIND` staleness and `BLOCKED`), the head still equals the run's head
    SHA, and no `do-not-merge` label is present;
  - anything else prints the reason and exits 0 — "not green-and-clean" is a deferral to a human, never a
    failing run;
  - merges with `gh pr merge --squash --delete-branch --match-head-commit <sha>` under
    `secrets.BUMP_TOKEN` (the owner PAT), then runs `make verify-closure`.
- **`scripts/verify_closure.py` + `make verify-closure PR=<n>` (new)** — after a merge, read
  `gh pr view <n> --json closingIssuesReferences` and fail, naming the issue, when the PR claimed a
  closing reference that is still `OPEN`. `.PHONY`, documented, and reachable from `ci-unit`.
- **`AGENTS.md`** — rule 7 becomes the new policy: the repo's CI merges a green, conflict-free,
  same-repo, non-draft PR; the agent still never runs `gh pr merge` itself and still stops at the
  reviewable PR; `do-not-merge` is the human's hold. The "PR review comments" section's
  "an APPROVED PR is merged" paragraph is reconciled with it so the file states one rule.
- **`tests/test_auto_merge.py` (new)** — the job's shape and every guard, read from the real YAML plus the
  real `verify_closure` code: needs every PR-relevant job, `pull_request`-only, same-repo-only,
  non-draft-only, `CLEAN`-only, head-pinned, PAT-not-`github.token`, `do-not-merge` honoured,
  `make verify-closure` called, and `AGENTS.md` carrying the new rule with the old wording gone.
- **`README.md` + `agent-wiki/`** — the policy, and how to hold a PR.

## Impact

- A green, conflict-free same-repo PR lands without waiting for a human; a red, conflicted, stale, blocked,
  draft or fork PR is untouched and still needs a person.
- The merge is a squash with the branch deleted, so `main` stays one commit per change and no stale branch
  lingers.
- The post-merge run on `main` still happens (owner PAT), so the GHCR publish path is unchanged.
- `do-not-merge` is the escape hatch: a reviewer mid-read holds a PR without touching CI.
