# 2026-11-21 — a green default-branch run never posts a red ci-verdict row (issue #2993, PR #<TBD>)

`main` repeated red `ci-verdict` runs and red `ci-verdict` rows at each new tip while main's own CI
was green. Measured at main `a4afb185e23900412a5a7a337069daf08324e214`: verdict run `44823923197`
judged main's CI push run `44819931621` (`run ... head=a4afb18 event=push branch=main
conclusion=success`, 9 judged jobs green) and posted `conclusion=failure` (artifact
`136591838065`) solely because the head carried issue-bot `implement` failures — run `44822618375`
(row `136589325345`, superseded) and run `44822619990` (row `136589328437`, named as the blocker).

## What was verified

- The #2116 forcing exists to protect MERGE decisions: `auto_merge.py` refuses any red check-run at
  a PR head. A `main` commit gates no merge at all — the same forcing there reddens nothing and just
  trains readers to ignore a red `ci-verdict` where it really does hold a merge.
- `scripts/ci_verdict.py` reads the judged run's `event` from the fetched run record; a
  `--run-event` / `CI_VERDICT_RUN_EVENT` knob replays it without the API. `run_event` outside
  `("", "pull_request")` + GREEN judged verdict + unjudged reds -> posted conclusion `neutral`,
  exit 0, plus a `DEFAULT-BRANCH HEAD` line naming the event, the rule, and every unjudged red it
  is not reddening. An empty event (a replay with no stated event) keeps the strict PR-head case.
- Unchanged on purpose: `success` only for a head with NO red named; `failure` whenever the judged
  verdict itself is not GREEN (a push run whose own judged job failed stays red); the superseded-row
  collapse (#2885) still runs before the arm; every unjudged red stays fully named.
- 4 new tests in `tests/test_ci_verdict.py` replay the exact measured row set via the real CLI:
  push event -> neutral + DEFAULT-BRANCH line; no event -> failure; `pull_request` event -> failure
  (#2116 pinned); push + `ci-images` judged failure -> failure with no neutral line. The neutral
  fixture reproduces the superseded collapse (`44822618375` cleared by `44822619990`) exactly as the
  production log recorded it.

## Key decisions

- `neutral`, not `success`: the head really does carry reds (bot-lane failures); the verdict's job
  is to say so without pretending a default-branch head is blocked or clean. The green main-push run
  at `369a33279` keeps posting truthfully either way.
- The event, not the branch name, decides: the run record GitHub gives the verdict already carries
  it (`ci-verdict.yml` passes the judged `RUN_ID`), so no new API surface and no workflow change.

## Current status

Fix implemented in `scripts/ci_verdict.py`; docs updated (`ci-verdict.yml` header,
`docs/ARCHITECTURE.md` verdict section). The two companion defects measured the same night are
separate filed issues: #2991 (the merge sweep defers on a stale `ci-verdict` row its own verdict
replaces seconds later) and #2992 (a CI run with a stalled `in_progress` job silences the verdict
and merge sweep until it concludes).
