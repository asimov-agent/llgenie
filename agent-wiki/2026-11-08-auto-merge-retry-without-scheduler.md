# The merge retry no longer depends on a scheduler that fires 4x/day (issue #2101)

## The three measured facts

Measured 2026-11-08 at `origin/main` `ea8c239e`.

### 1. Every scheduled workflow in this repo under-fires, whatever its cron says

`auto-merge.yml` declares `3,33 * * * *` — 48 slots/day. It receives 3–5/day:

```
10-23=3 10-24=7 10-25=7 10-26=5 10-27=5 10-28=3 10-29=4 10-30=5
10-31=5 11-01=5 11-02=3 11-03=3 11-04=4 11-05=4 11-06=4 11-07=4
```

The gap distribution over all 72 schedule runs: **median 5.01 h, minimum 2.05 h, and ZERO gaps under
one hour** (7 in 1–3 h, 41 in 3–6 h, 23 over 6 h). A 30-minute cron cannot produce zero sub-hour
gaps.

**It is the scheduler, not runner starvation.** Three independent signatures:

- **No schedule run is ever cancelled.** `auto-merge`: `success=72`, `cancelled=0`. A starved run
  shows up as queued or cancelled; these were created and ran.
- **The queue lag is zero.** `created_at → run_started_at` median **0.0 min** (max 195 min). The
  runs that DO exist start immediately — they are not waiting for a runner.
- **`created_at` minutes are scattered**, not pinned to the requested `:03`/`:33`. Over 72 runs the
  minute histogram is spread across 43 distinct minutes (`:40` ×5, `:50` ×5, `:51` ×4, `:54` ×4, …).
  That is GitHub creating the run late, not the cron firing on time into a queue.

**And it is repo-wide, not this workflow.** The comparators the issue cited (`schedule=51`,
`schedule=86`) are *totals*, not rates. Their actual rates:

| workflow | cron | declared/day | measured/day | median gap |
|---|---|---|---|---|
| `auto-merge` | `3,33 * * * *` | 48 | 3–5 | 5.01 h |
| `queued-alarm` | `7,37 * * * *` | 48 | 5–8 | 4.28 h |
| `fix-bot` | `17 * * * *` | 24 | 4–7 | 4.56 h |
| `issue-refiner` | `43 * * * *` | 24 | 4–7 | — |
| `rebase-bot` | `29 */6 * * *` | 4 | ~3.5 | **6.81 h** |

Every high-frequency cron collapses to ~4–8 runs/day regardless of what it declares, while the ONE
cron that asks for fewer than ~5/day (`rebase-bot`, 4/day) is met at 6.81 h. So the cap is on the
scheduler's side and **cannot be fixed from this file or any workflow file**. The honest conclusion
is the issue's own alternative: the workflow must not CLAIM 48/day, and nothing may DEPEND on it.

### 2. 41% of sweeps are cancelled, and the justification for it was false

```
last 100 auto-merge runs: success=59  cancelled=41
```

The in-file comment justified `cancel-in-progress: true` with *"a PR whose sweep is preempted is
picked up by the next sweep, including the scheduled recheck"*. At 4–5 rechecks/day that sentence
describes a net that does not exist, and a green head produces no further CI completion to fire
"the next sweep" — so a cancelled sweep was simply lost.

### 3. `#2069` lost a fully-green armed head

Head `cc72588c`, all 16 checks `success`, armed. Deferred for *"still has an unfinished run
(in_progress)"* (#1551). That row then finished green **without** producing a completion this
workflow watches, so nothing re-decided it; the next recheck was hours away; at `04:02:38Z` the
rebase lane force-pushed `cc72588c → fbbc29a6` and the verified green tree was discarded, re-running
16 jobs.

## The fix: the retry does not depend on the scheduler

1. **`settle_unfinished_head()`** — a mid-flight deferral now waits for ITS OWN row to conclude,
   bounded (`SETTLE_ATTEMPTS=6` × 30 s = 3 min, well inside the job's 10-minute timeout), and
   re-asks `no_concluded_green` each time. If the row concluded green the head is merged **in the
   same run**. This is the #2069 shape: no event is waited for. It does NOT weaken #1551 — a head
   with a genuinely unfinished run is still never merged.
2. **The recheck sweeps marker-free green heads.** `recheck()` gained a `green_unmarked` class: any
   open PR whose current head has a concluded green run and no red check is decided even with no
   deferral marker, because a **cancelled sweep posts no marker** — so a marker-only net is blind to
   exactly the population the 41% cancellation produces. The negative controls are unchanged: a red
   head, or a head with no concluded green run, is still refused.
3. **`MAX_RECHECK_PRS = 50`** (was 5) — 12 open PRs against a cap of 5 starved 7 of them every sweep.
   The sweep is idempotent (it re-reads live state, each merge is one atomic `gh pr merge`), so a
   higher bound costs reads, never extra merges.
4. **The retry job can no longer be cancelled by what it retries.** `concurrency:` moved from the
   WORKFLOW onto the `merge` JOB (keeping `cancel-in-progress: true` there, which is correct — a
   sweep supersedes an older sweep), and `recheck` got its own group `auto-merge-recheck` with
   `cancel-in-progress: false`. Before this, `cancel-in-progress: true` at workflow level cancelled
   the ENTIRE run — so the 41% cancellation rate was cancelling the recovery pass along with the
   attempt it exists to recover. A retry that dies with the thing it retries is not a retry.
5. **The recheck does not settle per PR — 50 heads × the 3-minute bound is 150 minutes against that
   job's 10-minute timeout.** Only the single-PR `merge` job waits for its own unfinished row;
   `recheck` takes the fast read (`settle=False`) and lets the next pass, or the merge job's in-run
   settle, do the waiting. Otherwise the retry would be killed by its own patience.
6. **The false justification is replaced by the measurement** in both the schedule block and the
   concurrency block, and the file no longer claims 30-minute coverage.

## What was deliberately NOT done

- **`#1386` (green-only gate) and `#1551` (mid-flight rule) are untouched.** No gate was relaxed;
  the change adds a bounded re-ask and widens which PRs are *considered*, not what counts as green.
- **The cron was not "fixed"** — it cannot be, per the measurements above. The dependency on it was
  removed instead.
- **`cancel-in-progress: true` is retained**, and now it is retained honestly: the recovery path
  works in-run and marker-free rather than by hoping for a scheduled sweep.
- **AC7 is enforced in CODE, not in another lane's SOUL.** The first draft declared it a behaviour of
  `agents/llgenie-pr-merge-conflict/` and handed it off — but the thing that actually discards a green
  tree is `scripts/rebase_bot_sweep.py`, which is this lane's own file. `armed_green_head()` now reads
  `autoMergeRequest` + `mergeable` + the head's checks, and the sweep passes over a head that is
  ARMED and settled-green, recording the mergeability answer it measured. That is AC7's "recording a
  mergeability check at that head first" made mechanical: an unarmed or armed-but-red head is still
  rebased (the negative controls), so nothing is starved by the guard.

## Proof

- `tests/test_auto_merge.py` + `tests/test_ci_concurrency.py`: **105 passed**.
- **Mutation-proved three ways**, each reverted separately and red: dropping `green_unmarked` reds
  the markerless-merge test; restoring the cap of 5 reds the twelve-PR test; and changing `run()`
  back to the bare `no_concluded_green` reds `test_run_itself_waits_for_an_unfinished_row_and_then_merges`
  (it reproduces the exact #2069 deferral line: *"still has an unfinished run (in_progress) … not
  merged (issue #1551)"*).

## Files

- `scripts/auto_merge.py` — `settle_unfinished_head()`, `SETTLE_ATTEMPTS`/`SETTLE_DELAY_S`,
  `MAX_RECHECK_PRS`, the `green_unmarked` recheck class, CLI default.
- `.github/workflows/auto-merge.yml` — measured-truth comments in the schedule and concurrency
  blocks; `MAX=50` on the recheck step.
- `Makefile` — `auto-merge-recheck` default `MAX=50` and its `##` line.
- `tests/test_auto_merge.py` — a sequenced `runs` fake plus six new/updated tests.
