# Issue-bot close→hold: an OPEN implementing PR keeps its issue open (#2869)

Issue: #2869. OpenSpec change: issue-bot-leave-open-2869 (specs/bot-issue-close-discipline).

## What was verified
- Root cause (measured on the #2048 timeline): `apply_verdict` files EVERY lane close with
  `gh issue close --reason "not planned"`. #2048 was closed `not planned` by the lane while
  PR #2863 — the PR whose body carries `closes #2048` — was OPEN and mid-landing. The merge
  later re-filed it `completed`, but the lane's verdict had already decided the issue was
  unwanted work.
- Fix class in `scripts/issue_implementer.py`: `hold` is a fourth verdict (`VERDICTS`,
  `TRIAGE: hold` in the decision block). `open_implementing_pr()` resolves every number the
  EVIDENCE cites through `gh api pulls/<n>` and asks whether that PR is OPEN and claims this
  issue — using the gate's OWN grammar (`check_pr_closing.closing_references /
  issue_line_claims / subject_claims`), so lane and closing gate cannot disagree about what a
  claim is; a `does not close #N` disqualification is not a claim. A `close` whose evidence
  names such a PR converts to a hold; a bare `hold` with no OPEN claiming PR is refused.
- `apply_hold()` leaves the issue OPEN, posts one comment naming the PR (carrying the
  `bot-done` claim release), and strips the queue labels so the picker cannot re-pick it.
  The issue's `completed` close belongs to the PR's closing reference at merge.
- New read `scripts/bot_close_reasons.py` + `make bot-close-reasons-report`: walks merged
  PRs' closing references onto issues, prints every lane-closed one with its `state_reason`,
  and FLAGS a `not_planned` closure contradicted by a merged PR. Live run at this tree:
  `merged_prs_read=250 issues_claimed=223 bot_closed_rows=1 flagged=0` — no live
  contradiction remains; #2048 reads `completed` (timeline: lane closed `not_planned`, the
  merge re-filed `completed`).
- Playbooks pinned to the rule: `.hermes/skills/issue-triage/SKILL.md` (v1.1.0, verdict
  vocabulary + close/hold rule), the planner `github-issue-triage` skill (close-reason table
  row `implemented (PR OPEN)` + open-PR-board section), and the implementer's
  `references/planner-stale-state.md`.

## Key decisions
- Grammar unification: the hold guard delegates to `check_pr_closing.py` instead of
  re-detecting claims; `issue_implementer -> check_pr_closing` and
  `bot_close_reasons -> check_pr_closing` registered in `scripts/package-layers.json`.
- An OPEN PR claiming a DIFFERENT issue, a closed PR, and a negated `does not close`
  reference all still permit a normal close — the guard is per-issue (tests pin all three).

## Current status
- Tests: `tests/test_issue_implementer.py` (+7 hold/close-guard cases) and new
  `tests/test_bot_close_reasons.py` (hermetic fake-`gh` answering the exact `gh api` paths;
  also asserts the make-target wiring, layer registration, and the three playbook texts).
- Lane remains dispatch-only (issue #2701 discipline); the report is on-demand.
