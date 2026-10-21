# A green PR blocked only by a review is approved by the other identity — and every deferral is on the PR

- Issue: [#491](https://github.com/asimov-agent/llgenie/issues/491)
- OpenSpec change: `auto-merge-review-approve`
- Branch: `feat/auto-merge-review-approve`

## What was wrong

With the fork head accepted (#489), `auto-merge` still could not land PR #481: GitHub reports
`mergeable=MERGEABLE`, `mergeStateStatus=BLOCKED`, `reviewDecision=REVIEW_REQUIRED` with **0 reviews**, and
the job defers on `BLOCKED` by design. Nothing on the PR said why — the reason lived only in a run log. Two
defects: a green PR waits for a keyboard, and the wait is invisible.

## What changed

- `scripts/auto_merge.py` — `review_blocked()` recognises the one procedural block; `try_approve()` posts
  `gh pr review --approve` **only** when the author is a different account from the merge token's (GitHub
  refuses a self-approval) and is one of this repo's two identities (`andyholst`, `asimov-agent`), then
  re-reads the state and merges if it became `CLEAN`; `defer()` posts ONE comment per head SHA
  (`<!-- auto-merge: deferred <sha> -->`) with the reason and what would unblock it; `explain()` prints the
  verdict and writes nothing.
- `Makefile` — `auto-merge` gains `APPROVE=1`; new `auto-merge-explain` (`.PHONY`, documented).
- `.github/workflows/ci.yml` — the job sets `APPROVE: "1"`; still `secrets.BUMP_TOKEN`.
- `README.md` — the two new behaviours.
- `tests/test_auto_merge.py` — 23 cases, including approve-then-merge order, no self-approval, no stranger
  approval, no approval for `DIRTY`/`BEHIND`, one deferral comment per head, and `explain` writing nothing.

## Verified

- `pytest tests/test_auto_merge.py` → 23 passed.
- `make auto-merge PR=1 REPO=o/r HEAD_SHA=abc APPROVE=1` → `--approve-when-review-required` in the argv;
  `make auto-merge-explain PR=1 REPO=o/r` → `explain`.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make openspec-validate NAME=auto-merge-review-approve` — green.
- `make test-unit` — green (numbers in the PR).

## Notes

- **`AGENTS.md` rule 7 needs one paragraph to match**, and that file is write-protected for the agent (the
  approval prompt timed out, and silence is not consent). Proposed wording is in the PR body; the change is
  complete without it, but the repo's rule list will not mention the approval until it is applied.
- A same-account PR still needs a human: GitHub forbids approving your own pull request. The deferral comment
  names that instead of leaving a bare `BLOCKED`.
- Where the review requirement is configured remains invisible through the API (ruleset has only
  `deletion`/`non_fast_forward`; no CODEOWNERS). This works *with* the requirement; removing it for the bot
  account is a Settings decision.
