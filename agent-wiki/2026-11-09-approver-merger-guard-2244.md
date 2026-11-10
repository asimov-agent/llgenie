# review-verdict names the true review author — approver != merger (issue #2244) — 2026-11-09

**Implements:** issue #2244 · **PR:** #2372

The #2187/#2239 acceptance gate let a PR close an issue with an unticked
`## Acceptance criteria` box when the head carried a `bot-verdict` APPROVE
marker at that exact head — reported `acceptance-proven-awaiting-writer`
instead of red. That marker was posted by `review-verdict.yml` on ANY
`pull_request_review: submitted` with state `approved`, and it hardcoded
`reviewer=github-actions[bot]` (line 131), whatever identity actually
submitted the review. `auto_merge.try_approve`
(`scripts/auto_merge.py:412-445`) posts `gh pr review --approve` with the
merge token to clear a review block; that approval is itself a submitted
review, so it seeded the SAME trusted marker the acceptance gate now trusts —
the merger approving its own gate evidence, the #1088 class (approver==merger),
and the #1088 rule was never checked.

This change stops that:

- `review-verdict.yml` now captures the TRUE review author
  (`github.event.review.user.login`) into the marker's `reviewer=` slot and
  DROPS an approve review authored by a merge-path identity
  (`asimov-agent` = the owner PAT that merges, `github-actions[bot]` = the
  job/APPROVER token) — an approve verdict must be
  `reviewer==author==a distinct reviewer identity`.
- `scripts/bot_verdict.py` adds `MERGER_LOGINS` + `allowed_reviewer`, and
  `verdict_for_head` now rejects an ACCEPTING verdict whose `reviewer=` is a
  merge-path identity (approver != merger) and accepts the review-verdict
  workflow relay only when the named reviewer is a genuinely distinct identity;
  a `changes` verdict from any trusted reviewer still holds the PR (safe
  direction). `post()` dedupes on the marker itself, not the comment author.
- `scripts/check_pr_acceptance.py::verdict_evidence` adds a defense-in-depth
  reject of a merger `reviewer=`.
- Tests gain the approver!=merger negative + positive controls in
  `tests/test_bot_verdict.py`, `tests/test_check_pr_acceptance.py` and
  `tests/test_auto_merge.py` (the negative controls FAIL against the pre-fix
  `origin/main 005d457` tree and pass at this head). `docs/BOTS.md` updated to
  the new trust model.

Result: an unticked acceptance box stays `unproven` (red) unless a genuinely
distinct reviewer approved it at the head; auto-merge's own gate-clearing
approval can no longer manufacture the acceptance evidence that satisfies the
gate, while a real approve from a distinct reviewer (`andyholst` or a dedicated
reviewer bot) still reports `acceptance-proven-awaiting-writer` (#2187 kept).
