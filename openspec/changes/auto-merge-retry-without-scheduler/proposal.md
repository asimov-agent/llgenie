## Why

The fleet auto-merges a bot PR on green. The machinery works (`#2065` approved `03:43:09Z`, merged
`03:43:13Z`), but the RETRY path does not, and a green armed PR can sit for hours and then lose its
green. Measured 2026-11-08 at `origin/main` `ea8c239e`.

**The scheduled recheck fires ~4–5×/day, not 48.** `3,33 * * * *` declares 48 slots; the workflow
received 3–5/day across eight measured days, with a median gap of **5.01 h** and **zero gaps under
one hour**. This is the GitHub scheduler dropping slots, not runner starvation: **no schedule run
was ever cancelled** (`success=72, cancelled=0`) and the `created_at → run_started_at` lag is a
median of **0.0 min** (the runs that exist start immediately), with `created_at` minutes scattered
across 43 distinct values rather than pinned to `:03`/`:33`. It is also repo-wide: every
high-frequency cron here collapses to 4–8 runs/day (`fix-bot` hourly → 4–7; `queued-alarm` 48/day →
5–8) while the one cron asking for <5/day (`rebase-bot`, 4/day) is met at 6.81 h. So no workflow
file can fix the rate.

**41% of sweep runs are cancelled** by `group: auto-merge-${{ … }}` + `cancel-in-progress: true`,
and the in-file justification ("picked up by the next sweep, including the scheduled recheck") is
false at 4/day — a green head produces no further CI completion, so "the next sweep" never fires.

**The casualty, measured:** `#2069` head `cc72588c`, 16/16 checks `success`, armed; deferred for
"still has an unfinished run (in_progress)" (#1551); that row then finished green with no completion
event; the recheck was hours away; at `04:02:38Z` a rebase force-pushed the green head away and
re-ran 16 jobs. Plus `--max-prs 5` against 12 open PRs, and a recheck blind to any PR with no
deferral marker — which is exactly what a cancelled sweep leaves behind.

## What changes

- `settle_unfinished_head()` — a mid-flight deferral waits for ITS OWN row to conclude, bounded
  (`6 × 30 s = 3 min`, inside the job's 10-minute timeout), re-asking the verdict each time. If the
  row concluded green, the head is merged **in the same run**. No event is waited for.
- `recheck()` gains a `green_unmarked` class: any open PR whose current head has a concluded green
  run and no red check is decided even with no deferral marker.
- `MAX_RECHECK_PRS = 50` (was 5) so a 12-PR board is covered, not starved.
- The false justification is replaced by the measurement in the schedule and concurrency blocks; the
  file no longer claims 30-minute coverage.

## What does not change

- **`#1386` (green-only merge gate) and `#1551` (mid-flight head) are untouched.** A head with a
  genuinely unfinished run is still never merged, and no definition of "green" is relaxed. The
  change adds a bounded re-ask and widens which PRs are *considered*.
- `cancel-in-progress: true` is retained — now justified by a recovery path that works in-run and
  marker-free rather than by hope in a scheduled sweep.
- The cron is unchanged: it cannot be fixed from this file, so nothing depends on it.

## Out of scope

The rebase lane's rule "do not rebase a green, armed, deferral-only head without a mergeability
check" is a behaviour of `agents/llgenie-pr-merge-conflict/`, which changes by issue+PR under that
profile rather than by an edit from this lane.
