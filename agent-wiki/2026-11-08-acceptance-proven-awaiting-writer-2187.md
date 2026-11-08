# the acceptance gate names "proven, awaiting the verdict-writer" (issue #2187) — 2026-11-08

**Implements:** issue #2187 — `check-pr-acceptance` could distinguish ONLY two states of an issue's
`## Acceptance criteria`: ticked or unticked. The only writer that turns `- [ ]` into `- [x]` is
`acceptance_writeback.py` (issue #1644) invoked by `review_finalize.py` (issue #1808); neither is
mounted in any workflow (`grep -rn 'acceptance_writeback|review_finalize' .github/workflows/` returns
zero hits). So a PR whose criteria ARE proven by a reviewer's COMMENTED verdict — but whose write-back
has not yet PATCHed the issue body — read exactly like an unproven PR: three open PRs red `guard` +
`scope` on the same gate simultaneously (#2183/#2188/#2167), each failing `make check-pr-acceptance`
with "acceptance item … is still `- [ ]`".

Measured live at main@d4e1f376 (2026-11-08): the gate's ✓ok path could not tell `- [ ]` + no verdict
(genuinely unproven) from `- [ ]` + a trusted approve verdict at the current head (proven, awaiting the
verdict-writer).

## What changed

- **`scripts/check_pr_acceptance.py`** — the three-state gate. New `verdict_evidence(gh, repo, pr,
  head)` reads the PR's comment trail through the existing #852 `bot_verdict.verdict_for_head`
  (trusted author, `reviewer == author`, EXACT current-head match) and returns the ACCEPTING verdict.
  `acceptance_verdict(..., verdict=)` reports an unticked criterion under a trusted approve verdict at
  the current head as `acceptance-proven-awaiting-writer` — a distinct, NON-red finding — instead of
  `acceptance-unchecked`. A `changes` verdict, a verdict at another head, or an unreadable comment trail
  all return NO evidence, so the box stays genuinely `unproven` (red). `main` threads `--pr` and exits
  non-zero only when a BLOCKING finding exists — a verdict-proven-but-unticked box never reds, a genuine
  unproven box still does. One verdict read per run (a PR property shared across every linked issue).
- **`Makefile` `check-pr-acceptance`** — passes `--pr "$(PR_NUMBER)"`, so the guard/scope jobs hand the
  gate the PR number it needs to read the trail (the env already carried `PR_NUMBER`/`PR_REPO`).
- **`docs/BOTS.md`** — documents the third state and the negative controls.
- **`tests/test_check_pr_acceptance.py`** — eight new hermetic tests: the three states, the `changes`
  verdict and wrong-head negative controls, and CLI-level proof via a fake `gh` serving both the live
  issue read and the verdict comment trail.
- **`openspec/changes/acceptance-proven-awaiting-writer/`** — the required OpenSpec change
  (proposal + spec + tasks).

## Decisions

- **The gate reads the verdict comment as evidence** — the task offered two re-triggers for the
  write-back; this is the second, and it keeps the gate verdict-driven (#1644's gate is untouched while
  no write-back is mounted in a workflow). A ticked box is no longer a prerequisite to re-run CI; the
  write-back lands when the verdict-writer is free, without a push.
- **Only ACCEPTING verdicts count.** `changes`/reject is a second opinion that asks for work, never
  proof; `bot_verdict.ACCEPTING` is the same set `auto_merge` accepts.
- **`blocking:` is now a finding field** so render + exit agree: `acceptance-proven-awaiting-writer`
  carries `blocking: False`; every genuinely-unproven finding (unchecked, exceeds, tick-unprovable,
  heading-masked, rollout-lane-open, issue-unreadable) carries `blocking: True`. The negative control is
  the whole point: no verdict, a `changes` verdict, or a stale head still exits non-zero.
- **Proven does not mean ticked.** The gate never ticks a box; it only re-clerks unproven. The write-back
  seam (#1644) is untouched, so an auto-merged PR with no verdict still ticks nothing (#1088-class).

Refs: #2187 (this issue), #1644/#1808 (the write-back seam it names), #852 (the verdict marker), #1792/
#745 (the acceptance gate it sharpens).
