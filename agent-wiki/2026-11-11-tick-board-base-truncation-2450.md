# tick-board-base-truncation: staleness measured independent of short-sha truncation (#2450, #2496)

Date: 2026-11-11. OpenSpec change: `tick-board-base-truncation`. PR: #2496. Issue: #2450.

## What was verified

- The defect, measured on `main` at `23faf9550` (9 chars at this repo's object count):
  `tick_board.sh` section B truncated `baseRefOid` to 8 chars (`[:8]`) but compared it against
  the freshly fetched `MAIN` at its full short length — `23faf955` vs `23faf9550` — so every
  current-main PR read STALE. The four proven base-CLEAN PRs #2448 #2438 #2365 #2363
  (`git merge-base --is-ancestor`-verified) all printed STALE on the 2026-11-10 board run.
  Section F carried the same class of comparison (`(headSha)[:8] == main`), so its TIP tag
  could never be true at a 9-char main.
- The fix: both sections now decide by a sha-prefix rule — two names denote the SAME commit
  when either contains the other (40-char base vs 9-char main, 8-char vs 8-char, any length);
  STALE only when the prefixes genuinely differ, and the true base is still printed.
  Section F gained a `RUN_LIST_JSON` fixture (same pattern as section B's `PR_LIST_JSON`) so
  the TIP tag is hermetically testable.
- New hermetic tests in the existing module: a 40-char + a 9-char base at a 9-char main both
  read fresh with their true bases printed; a genuinely stale 40-char base still reads STALE;
  a 40-char `headSha` at the 9-char main tip tags TIP and an older head tags other.
- Regression surface unchanged: the #2159 fixture board (8-char main) still reads 12 stale of
  14 dirty 2; `test_tick_board_arm.py` and `test_tick_board_ownership.py` untouched.
  20/20 tick tests in `llgenie/test` at this head; `make openspec-validate` exits 0.

## Current status

OpenSpec `tick-board-base-truncation` validated (ADDED requirements: length-robust staleness,
length-robust TIP tag, all with Given/When/Then). PR #2496 carries the change; `tasks.md` 1–3
ticked at the test head, 4–5 tick after the docs commit and preflight on the final head.
