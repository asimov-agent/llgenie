# tick-board-base-truncation

## Why

`tick_board.sh` section B truncates `baseRefOid` to 8 chars (`[:8]`) but compares it against the
fetched main sha `MAIN` at its full short length — 9 chars at this repo's object count (issue #2450,
measured 2026-11-10 at main `23faf9550`): a PR whose base IS current main reads `base=23faf955` vs
main `23faf9550`, so `is_stale = base != main` is True. All four proven base-CLEAN PRs (#2448,
#2438, #2365, #2363, verified with `git merge-base --is-ancestor`) were reported STALE. The board's
stale count then sends the rebase lane to branches that do not need rebasing (no-op force-pushes,
merges that can discard a green) and mis-states every planner pass report. Section F carries the
same class of comparison (`(headSha)[:8] == main`), so its TIP tag can never be true at a 9-char
main either.

## What Changes

- Section B's staleness decision becomes truncation-robust: the PR base and main are treated as the
  SAME commit when either sha string contains the other as a prefix (8-char base vs 9-char main,
  full-length base vs short-form main); STALE only when the prefixes genuinely differ, and the true
  base is still printed.
- Section F's TIP tag uses the same length-robust comparison, so a run at the main tip reads TIP at
  any short-sha length.
- The existing hermetic tick tests are extended (not replaced): a 9-char main with a full-length
  base must read fresh; a genuinely stale base must still read STALE; the arm classification stays
  byte-identical.

## Impact

- Modified: `agents/llgenie-planner/scripts/tick_board.sh` (section B staleness line, section F TIP tag)
- Tests: `tests/test_tick_board.py` (new truncation scenarios against the same fixture surface)
- Closes GitHub issue #2450.
