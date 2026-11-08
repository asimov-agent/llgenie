# acceptance-proven-awaiting-writer — Tasks

Issue: [#2187](https://github.com/asimov-agent/llgenie/issues/2187)

- [x] 1. `scripts/check_pr_acceptance.py` reads the PR's trusted verdict trail (`verdict_evidence` →
      `bot_verdict.verdict_for_head`, ACCEPTING-only, exact-head) so an unticked criterion under a
      trusted approve verdict at the current head is `acceptance-proven-awaiting-writer` (distinct,
      non-red), and a genuinely unproven box stays `acceptance-unchecked` (red). A `changes` verdict,
      a wrong-head verdict, and an unreadable comment trail all return no evidence. `main` threads
      `--pr` and exits non-zero only on a BLOCKING finding.
- [x] 2. `Makefile` `check-pr-acceptance` passes `--pr "$(PR_NUMBER)"`, so the ci.yml/scope.yml guard
      steps hand the gate the PR number needed to read the verdict trail.
- [x] 3. `tests/test_check_pr_acceptance.py` covers the three states (unproven red / proven-awaiting
      green / proven-ticked green), the `changes`-verdict negative control, the wrong-head negative
      control, and CLI-level proof via a fake `gh` serving the issue read + the verdict comment trail.
      Verified: 44/44 module tests pass in llgenie/test (62/62 with the bot-verdict suite).
