# 2026-11-28 — fix-bot must check the LIVE PR body (#3123)

Observed at head `8970eefca` on PR #3122: fix-bot runs `46132980221` and `46133842812` both
posted an ended-green outcome while `pre == post == 8970eefca`. The check loop never fetched the
live PR body — `PR_BODY` was only stamped in the final outcome step, after the verdict — so
body-dependent gates read an unset path and passed vacuously, producing a false `fixed` marker.

Fix: `.github/workflows/fix-bot.yml` now fetches `body`, `headRefOid` and `baseRefOid` into
`fix-bot-pr-body.md` and the `livebody` outputs BEFORE `fix-loop-image`, and passes
`PR_BODY`/`PR_HEAD`/`PR_BASE` into the loop. A body-dependent check with an empty body or missing
head/base exits with `exit=2` before `fix-loop-image`, so no `bot-done ... fixed` can be posted.
The scratch file is in the run-input block of `.gitignore` and the test roster.

Proof: both new workflow-shape tests fail on the old tree (`2 failed`) and pass on the fixed tree.
The extracted check-loop shell returns `rc=2` with `::error::body-dependent check ... refusing a
vacuous green (issue #3123)` and writes `exit=2` when the live body is empty.
