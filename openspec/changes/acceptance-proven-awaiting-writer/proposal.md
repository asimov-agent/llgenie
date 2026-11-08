# acceptance-proven-awaiting-writer — proposal

Issue: [#2187](https://github.com/asimov-agent/llgenie/issues/2187)

## Why

`make check-pr-acceptance` (Makefile:1130 → `scripts/check_pr_acceptance.py`) can distinguish ONLY two
states of an issue's `## Acceptance criteria`: ticked or unticked. The only writer that turns
`- [ ]` into `- [x]` is `acceptance_writeback.py` (issue #1644), invoked by `review_finalize.py`
(issue #1808), and neither is mounted in any workflow — `grep -rn 'acceptance_writeback|review_finalize'
.github/workflows/` returns zero hits. So a PR whose criteria ARE proven by a reviewer's COMMENTED
verdict, but whose write-back has not yet PATCHed the issue body, reads exactly like an unproven PR:
the gate reds `acceptance-unchecked`. There is no third state "proven, awaiting verdict-writer".

Measured live 2026-11-08 at main@d4e1f376: three open PRs red `guard` + `scope` on the SAME gate
simultaneously — #2183 (issue #2138), #2188 (issue #2165), #2167 (issue #2166) — each failing
`make check-pr-acceptance` with "acceptance item … is still `- [ ]`". The reviewer is the single
writer and the write-back has no CI-reachable trigger, so proven work reads as unproven on the board.

## What Changes

- `scripts/check_pr_acceptance.py`: a `verdict_evidence()` helper reads the PR's comment trail via
  `bot_verdict.verdict_for_head` (the trusted #852 marker: trusted author, reviewer == author, EXACT
  current-head match) and returns the approved verdict when it is ACCEPTING. `acceptance_verdict`
  gains a `verdict` parameter: an unticked criterion with a trusted approve verdict at the current
  head is reported `acceptance-proven-awaiting-writer` — a distinct, NON-red state — instead of
  `acceptance-unchecked`. A `changes` verdict, a wrong-head verdict, or an unreadable comment trail
  all return no evidence and the box stays `unproven` (red). `main` threads `--pr` (PR number) and
  exits non-zero only when a BLOCKING finding exists: a genuinely unproven box still reds; a
  verdict-proven-but-unticked box does not.
- `Makefile` `check-pr-acceptance`: passes `--pr "$(PR_NUMBER)"` so the guard/scope steps hand the
  gate the PR number it needs to read the verdict trail.
- `tests/test_check_pr_acceptance.py`: three-state tests (unproven red / proven-awaiting green /
  proven-ticked green), a `changes`-verdict negative control, a wrong-head negative control, and
  CLI-level tests driving a fake `gh` serving both the issue read and the verdict comment trail.

## Benefit

Proven-but-unticked work becomes distinguishable from unproven work at a glance: the gate reads the
verdict comment as evidence, so a ticked box is not required and the write-back no longer has to be
re-triggered by a push. The three stalled PRs gain a clear "proven, awaiting verdict-writer" signal
instead of a red `acceptance-unchecked`, and the write-back (or a re-prover) lands when the writer
is free — without weakening the gate's hold on a genuinely unproven close.
