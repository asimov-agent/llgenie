# PR/comment body must be prose, never a serialized `gh pr create` payload (issue #1638)

A PR body is the merge-owner's and reviewer's primary artifact — the one surface read to judge
what a change implements and whether it is safe to merge. #1637's body was, for its whole life,
a serialized `gh pr create` request object dumped into `.body`: it carried the real markdown on
the inside, so the old empty/placeholder-only hygiene gate stayed green while every reader saw the
raw API JSON in the review surface. Same defect class for a comment posted through `gh pr comment`
/ `gh issue comment` or `/issues/{n}/comments`.

`scripts/check_pr_hygiene.py` now refuses any message body that is a serialized JSON object —
begins with `{` and parses as a `dict`, or carries the `gh pr create` request keys (`title`,
`base`, `body`) — on both the PR-body path and the comment path, with named verdicts
(`pr-body-json`, `pr-comment-json`). A clean markdown body still passes (no false positive).
Regression fixture: the #1637 payload shape. Gate change only — `scripts/check_pr_hygiene.py` and
`tests/test_pr_hygiene.py`; no producer file, no workflow YAML, no gate weakened.
