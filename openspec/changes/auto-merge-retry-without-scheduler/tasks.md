## 1. The scheduler-independent retry (#2101)

- [x] Diagnose the cron under-fire: scheduler dropping slots repo-wide, not runner starvation
      (no cancelled schedule runs; median created→started lag 0.0 min; every high-frequency cron
      collapses to 4–8/day while a 4/day cron is met)
- [x] `settle_unfinished_head()` — bounded in-run wait for the head's own unfinished row
- [x] Wire it into `run()` in place of the bare `no_concluded_green` read
- [x] Bound the wait well under the job timeout (`6 × 30 s = 3 min` vs `timeout-minutes: 10`)

## 2. The recheck covers what a cancellation produces

- [x] `green_unmarked` class: decide a concluded-green head with no deferral marker
- [x] Keep the negative controls: a red head and a head with no concluded green run are refused
- [x] `MAX_RECHECK_PRS` 5 → 50 so all open PRs are evaluated (12 measured open)

## 3. The retry is not cancellable by what it retries

- [x] Move `concurrency:` from the workflow onto the `merge` job (keeps supersession of sweeps)
- [x] Give `recheck` its own group `auto-merge-recheck` with `cancel-in-progress: false`
- [x] Pin both in tests, and prove by mutation (reverting to workflow level reds 3 tests)

## 4. The documentation stops lying

- [x] Replace the false "picked up by the next sweep, including the scheduled recheck" comment
- [x] Remove the "every 30 minutes" claim from the schedule block
- [x] Record the measured rate, the non-cancellation, and the zero queue lag in both blocks

## 5. The rebase never discards an armed green head (AC7, enforced in code)

- [x] `armed_green_head()` in `scripts/rebase_bot_sweep.py` — reads `autoMergeRequest`, `mergeable`
      and the head's checks; skips an armed settled-green head and records the mergeability answer
- [x] Negative controls: an unarmed head is still rebased, and an armed-but-RED head is still rebased

## 6. Gates untouched

- [x] `#1386` green-only gate unchanged
- [x] `#1551` mid-flight rule unchanged (a genuinely unfinished run is still never merged)

## 7. Proof

- [x] `tests/test_auto_merge.py` + `tests/test_ci_concurrency.py`: 105 passed
- [x] Mutation-proved five ways (drop `green_unmarked`; restore cap 5; revert `run()` wiring;
      remove the armed-green guard)
- [x] Docs trio (#1123): this openspec change + `agent-wiki/` note + `docs/changes.d/` row
