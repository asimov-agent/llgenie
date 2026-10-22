# The merge job finds a fork PR

Issue: #503. PR: #504.

#502's CI run `39721034188` finished green. Auto-merge run `39724035827` died at the lookup:
`gh api repos/.../actions/runs/39721034188/pull_requests` returned 404, and `set -e` exited before the
fallback. The fallback's `--head owner:branch` matches a same-repo branch only, so it would have missed
the fork head too. `gh pr list --search head:fix/rebase-behind-despite-comment` returns #502.

The resolve step now tolerates the 404 and searches by branch, keeping the row owned by the run's head
owner.
