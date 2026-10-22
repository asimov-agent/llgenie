# The merge job finds a fork PR after its CI run goes green

## Why

PR #502's CI run `39721034188` finished `success` at 04:44. The auto-merge run `39724035827` started two
seconds later and died before merging anything:

```
RUN_ID: 39721034188
HEAD_OWNER: andyholst
HEAD_BRANCH: fix/rebase-behind-despite-comment
gh: Not Found (HTTP 404)
##[error]Process completed with exit code 1.
```

The step calls `gh api repos/$REPO/actions/runs/$RUN_ID/pull_requests` under `set -euo pipefail`. That
endpoint 404s for a fork `pull_request` run with this token, so the step exits before the fallback. The
fallback would not have found it either: `gh pr list --head andyholst:fix/rebase-behind-despite-comment`
returns nothing, because `--head owner:branch` matches a same-repo branch. The search qualifier finds it:
`gh pr list --search head:fix/rebase-behind-despite-comment` returns #502.

## What Changes

- **`.github/workflows/auto-merge.yml`** — the runs lookup tolerates a 404 (`|| true`), and the fallback
  searches by `head:<branch>` and keeps the row whose head owner is the run's head owner.
- **`tests/test_auto_merge.py`** — the workflow text carries both guards.

## Impact

- A green fork PR is resolved and merged instead of failing the run at the lookup.
- A 404 from the runs endpoint no longer hides the fallback.
