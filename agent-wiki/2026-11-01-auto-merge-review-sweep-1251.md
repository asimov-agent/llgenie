# Auto-merge sweep approves a green review-blocked pull request

Issue: #1251.

The recheck sweep only retried a pull request that already carried a deferral marker for its current head. A green pull request that was never deferred stayed `REVIEW_REQUIRED`. Several open pull requests were in that state with auto-merge already armed, and the merge job on the latest CI completion was skipped, so nothing approved them.

The sweep now runs the same approve-then-merge decision when the pull request is mergeable, `mergeStateStatus` is `BLOCKED`, and `reviewDecision` is `REVIEW_REQUIRED`. The approver stays the workflow token (`github-actions[bot]`). The merge stays on the owner token. A pull request that is not review-blocked and has no deferral marker is still left alone.

Measured on `main` before this change: pull request #1247 was green, auto-merge was armed, and `reviewDecision` was `REVIEW_REQUIRED`.
