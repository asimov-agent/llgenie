# A bot PR's body carries its own `## Acceptance criteria` `- [ ]` checklist

## Why

The owner's universal form rule (issue #1796) is that every issue a lane files AND every PR body it
opens carries a `## Acceptance criteria` section where each criterion is a `- [ ] ` markdown checkbox,
one per provable outcome — a criterion a reviewer cannot tick is not one (issue #745). The merge-time
`check-pr-acceptance` gate (issue #1792) verifies the *linked issue's* criteria are ticked at merge, so
a close of an un-proven issue does not verify green silently — but it is silent when the PR body itself
never had the boxes to tick. This change closes that body half: a bot-authored PR body with no (or an
empty) acceptance checklist is refused by the new `check-pr-acceptance-form` gate. The rule is stated
for the fleet lanes, so human-only ranges are skipped; the gate is verification/surface only — it never
blocks `#1088` auto-merge and never ticks a box (that stays #1644's verdict-gated write-back).

## Success criteria

- a bot PR body with no tickable `## Acceptance criteria` `- [ ]` checklist is refused, naming the rule
  and the remedy;
- a human-only range is skipped, never failed;
- `check-pr-acceptance` (#1792, merge-time issue-state) and `acceptance_writeback` (#1644) are reused,
  never restated, and unchanged;
- the gate is wired into both guard workflows beside `check-pr-sync-line`, with the live-body read
  (issue #1589), and runs BEFORE `check-pr-acceptance` so its verdict is not masked when the sibling
  issue-state gate reds on the introducing PR's own unticked issue boxes.
