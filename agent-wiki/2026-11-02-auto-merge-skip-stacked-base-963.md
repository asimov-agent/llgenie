# 2026-11-02 auto-merge refuses a stacked base and reports hand merges into one (issue #963)

#963: a stacked PR (base = another open PR, not `main`) could be merged **instantly and unreviewed** by
its author — measured 08:19:55Z, `#958` `gh pr merge --auto --squash` → MERGED the same second. The
required-check half (a `guard` check in ruleset `24862727`) is owner-only, tracked in #880 and carved out
of this change. The code half lands here: the merger refuses a non-`main` base, and a hand merge that lands
anyway is detectable.

- `scripts/auto_merge.py`: `baseRefName` joins `PR_VIEW_STATE_FIELDS`, and `decide()` defers any PR whose
  `baseRefName != "main"`, naming the base as the reason — so `make auto-merge` never arms/merges a stacked
  PR. New `stacked-merged` subcommand lists the PRs merged into a non-`main` base (author, head sha,
  check-runs count at that head; expected 0).
- `.github/workflows/auto-merge.yml`: the scheduled recheck job also runs `make stacked-merge-detect`
  (schedule-triggered only) so a hand merge into a stacked base shows up in the same sweep that owns the
  merge gate.
- `docs/BOTS.md`: one line states the rule — arm only on a PR whose base is `main`; a stacked PR arms on
  retarget.
- `tests/test_auto_merge.py`: the negative control (a non-`main`-base PR is armed and the merger skips it,
  never calling `pr merge`), plus the detector's name-the-merge and reports-zero scenarios and the
  BOTS.md one-line rule.

Verified: `pytest tests/test_auto_merge.py` green (89 passed) in the test container; `make check-workflows`,
`make check-wiring`, `make check-docs`, `make lint`, `make openspec-validate
NAME=auto-merge-skip-stacked-base` green.
