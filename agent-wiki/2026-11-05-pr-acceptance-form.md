# A bot PR's body carries its own `## Acceptance criteria` `- [ ]` checklist (issue #1796)

The owner's universal form rule: every issue a fleet lane files AND every PR body it opens has a
`## Acceptance criteria` section with each criterion a `- [ ]` markdown checkbox, one per provable
outcome — a criterion a reviewer cannot tick is not one (issue #745). The merge-time #1792 gate
verifies the *linked issue's* criteria are ticked at merge; this surface is the PR-BODY half: it
catches a bot-authored PR body that never had the boxes at all.

## What changed

`make check-pr-acceptance-form` is a `check_pr_hygiene.py acceptance-form` subcommand mounted in CI
beside `check-pr-acceptance`/`check-pr-closing`. It reuses `acceptance_writeback.acceptance_items`
(imported, never restated), is gated by `is_bot_pr` (a human-only range is skipped, exactly like
`check-pr-agents-line`), and reds a bot PR whose body has no or empty tickable acceptance checklist.
The step runs with the LIVE PR body fetched via `gh api` (issue #1589), so a body-only fix clears on
rerun; a push to main has no body and prints `nothing to validate`.

Verification/surface only: it never blocks #1088 auto-merge and never ticks a box — write-back stays
`acceptance_writeback`'s verdict-gated seam (issue #1644).
