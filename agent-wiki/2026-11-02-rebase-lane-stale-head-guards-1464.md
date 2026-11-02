# Rebase lane: stale-head disambiguation — state==MERGED-first + mtime-vs-mergedAt guards (#1464)

Carries issue #1464, the rebase lane's own-lane idle-audit finding (filed by llgenie-pr-merge-conflict,
implemented by llgenie-issse-implementer): two read-before-act guards for the #1015 CONFLICTING-only
rebase sweep, encoded in the lane skill so a future sweep cannot be handed the wrong work.

## The two guards

1. **state==MERGED-first (#1).** The per-PR sweep probe reads `gh pr view <n> --json state` BEFORE any
   merge-base/merge-tree; a MERGED PR short-circuits as "no rebase owed (state==MERGED)" regardless of
   how far its leftover branch ref trails. Measured on the #1411 class: a squash merge leaves the PR's
   branch ref at its pre-merge head, so `git merge-base(main, head)` legitimately reports "behind" on
   content already at main's tip — a dispatch reading only merge-base hands the lane a merged PR as an
   owed rebase, exactly what it must never accept. Documented in
   `references/sweep-mechanics.md` §1 (the probe that measures staleness by merge-base).
2. **mtime-vs-mergedAt (#4).** A post-merge gate re-read whose finding's live mtime is strictly newer
   than the fold's `mergedAt` is NEXT-FOLD drift, attributed to the owning lane, never misfiled as the
   landed fold's failure. Measured on the check_agent_profiles case: the no-args gate can print
   "FAIL, N findings" right after a fold lands because live lanes keep editing after the merge — a
   finding-count alone mislabels a landed fold as needing a re-fold. Documented in
   `references/measurement-and-readback.md`.

Out of scope: guards #2/#3/#5/#6 are already standing rules (context only, no code).

## Verification

`tests/test_rebase_lane_scripts.py` pins both guards in their reference homes (a future edit that
drops the state-first ordering or the strictly-newer rule reds CI). Gates green through `make`
preflight + test-unit; this PR closes #1464.
