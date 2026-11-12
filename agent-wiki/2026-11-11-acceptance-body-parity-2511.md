# 2026-11-11 — acceptance-body-parity: the closing PR body's checklist must not lag its issue (#2511)

Verified against the spec `openspec/changes/acceptance-body-parity`:

- Measured symptom: at main `614838fb8`, 4 of the 12 most recently merged PRs (#2507 #2498 #2496
  #2490) carry unticked `- [ ]` boxes in their own `## Acceptance criteria` while their closed
  issues were ticked. Audit method: `gh pr list --state merged --limit 12` + regex `^\s*- \[ \]`.
- Fix: `acceptance_verdict` in `scripts/check_pr_acceptance.py` gained the blocking finding
  `acceptance-body-lag` (`where: pr-body`) — a close whose PR body keeps an unticked copy of a
  criterion is red in the existing `guard` job (`make check-pr-acceptance`). Canonical-section-only
  scope via `_acceptance_items`; `## Not covered` + linked item exemption via
  `_declared_out_of_scope`. The reverse of `claim-exceeds`, which only read the other direction.
- Tests: 5 new states; `tests/test_check_pr_acceptance.py` 58 passed; sibling acceptance suites
  24 passed.
- Retro-fix: the four merged bodies get `gh pr edit` ticks mirroring the issue-side proven lines.
- Decision: AGENTS.md carries the durable lockstep rule, but AGENTS.md is approval-protected and
  the write prompt timed out without consent during implementation — the rule text is filed as
  companion issue #2512 and named in #2511's `Not covered`. My own sweep skill
  (`llgenie-pr-sweep`) already records the lockstep practice for future sweeps.
- Current status: gate + tests in-branch; body retro-fix and CI drive follow the task list.
