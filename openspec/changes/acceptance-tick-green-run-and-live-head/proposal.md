# A ticked acceptance criterion must cite a live-green run and a current head (issue #2288)

## Why

A write-back tick on an acceptance box passes the run-id branch of `check-pr-acceptance` — the
`(proven: … run=<id>/head=<sha>)` marker is accepted as provable — even when the cited run is a RED
by-design gate run and the cited head is NO LONGER the PR's live head. Measured in the 2026-11-09
evidence audit at `main@e34cfd2e` (posting on #2223): of 8 ticked write-back issue-PR pairs, 4 cite a
`run=` whose `gh run view` conclusion is `failure` — the by-design `check-pr-acceptance` guard red
that fires while the box is still unchecked — and all 8 tick heads differ from the current PR live
head. A reader trusting the tick's run id sees a red run and reads the box as failed, or trusts a run
at a head the PR has rebased away from and misjudges the live tree. "Proven" is not verifiable from
the tick alone.

## What changes

- **`scripts/check_pr_acceptance.py`** re-checks each TICKED criterion's cited `run=<id>` and
  `head=<sha>`/`live=<sha>` against the PRESENT tree at merge time. A cited run whose live
  `gh run view` conclusion is not `success` (unreadable included) is a NEW blocking
  `tick-red-run` finding; a cited head/live that is not the merge-time head is a NEW blocking
  `tick-stale-head` finding. A by-design guard-red run can therefore never stand as proof, and a
  rebased (stale) tick is held until re-ticked with the current head — never trusted as current.
- **`scripts/review_finalize.py`** (the #1808 seam that drives the write-back) appends the PR's live
  head as a `live=<sha>` twin beside every `head=<sha>` it writes (`with_live_head`), so the marker
  names the measured head AND the live head at measurement — a rebased tick is visible as stale from
  the issue thread alone.
- **Issue #2288 AC3**: the 11 measured red-run/stale ticks on #2296 (3), #2181 (6), #2061 (1) and
  #1558 (1) — all four cited runs concluded `failure` (verified live at `e34cfd2e`) and all heads
  are stale — now fail the gate (`tick-red-run`/`tick-stale-head`) and are recorded explicitly as
  stale in this change and `docs/BOTS.md`; re-ticking them is the write-back seam's job once a green
  run / current head exists.

## Benefit

A `(proven: …)` tick becomes evidence a reader can re-verify: it names a run that actually concluded
`success` at a head that is (or was, with `live=` recorded) current. A by-design-red gate run or a
rebased tree can never present as proof, so the board cannot read red-as-failed or stale-as-current.

## Tests

- `tests/test_check_pr_acceptance.py`: a successful cited run + matching live head is green; a cited
  run concluding `failure` holds as `tick-red-run`; a stale head holds as `tick-stale-head`; a
  `live=` twin equal to the merge head is green; a non-sha `--rev` skips only the staleness referee
  (the run re-check still runs).
- `tests/test_review_finalize.py`: `with_live_head` appends the live twin idempotently, leaves an
  already-`live=` ref unchanged, and leaves a no-`head=` reproducible-command tick alone.
