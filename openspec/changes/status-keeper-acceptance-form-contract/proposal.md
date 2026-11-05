# status-keeper-acceptance-form-contract — proposal

Issue: [#1812](https://github.com/asimov-agent/llgenie/issues/1812) · [#1796 #1](https://github.com/asimov-agent/llgenie/issues/1796)

## Why

Under the owner's universal form rule (#1796 #1 / #1812), every affected fleet lane must carry,
via #791, a stated form contract in its own versioned SKILL.md: every issue the lane files AND
every PR body it opens has a `## Acceptance criteria` section with each criterion a `- [ ]`
markdown checkbox, one per provable outcome; a criterion a reviewer cannot tick is not one (#745),
and each lane's changed skill is text-only under `agents/<lane>/`. The `llgenie-status-keeper`
lane's SKILL.md on `origin/main` (v1.0.0, dde5c9ec) did not carry the contract, leaving #1796 #1
un-tickable for this lane (the reviewer's #1804 verdict, comment 6669030076, held #1796 at 5/6).

## What Changes

- `agents/llgenie-status-keeper/skills/llgenie-status-keeper/SKILL.md`: fold the live lane skill
  (v1.1.0, 9416 b, ahead of the tree v1.0.0 by the delta/nerve/fan-out lessons) live→tree
  byte-identical, then add the `## Acceptance-criteria form contract (#1796 #1)` section stating
  the contract verbatim — every issue this lane files AND every PR body it opens carries a
  `## Acceptance criteria` section whose items are each a `- [ ]` markdown checkbox, one per
  provable outcome; a criterion a reviewer cannot tick is not one (#745). Version bumps 1.1.0 → 1.2.0.
- Text-only change under `agents/llgenie-status-keeper/` plus the #1123 change-note trio
  (`agent-wiki/` + `docs/changes.d/` + `CHANGES.md` regen). No change to `issue_body.py`,
  `acceptance_writeback`, or `auto-merge.yml` (#1644/#1088/#491 intact).
- Versioned via #791 with the SYNC line per #1724 (`make sync-agent-profile PROFILE=llgenie-status-keeper`).

## What Doesn't Change

- No gate code, no renderer, no merge/arm rule. This is purely the per-lane behavioural contract.
