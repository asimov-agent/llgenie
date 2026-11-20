# 2026-11-20 — the rebase sweep records its own pass on the tracker (issue #2950, PR #<TBD>)

The `rebase-bot` lane drains the backlog but wrote nothing durable: its counts lived only in the
run log. The merge lane gained its own record (issue #2652, `make auto-merge-recheck RECORD=`);
this is the linked side issue that gives the rebase lane the same evidence on the same tracker.

## What was verified

- `scripts/rebase_bot_sweep.py` main() prints one `deferred=#<n>` line per entry of the sweep's
  pre-computed deferred list (stdout readout only; decision semantics and the result dict are
  unchanged). Test: `test_sweep_prints_one_structured_line_per_deferred_pr`.
- `scripts/rebase_sweep_record.py` assembles exactly ONE comment: first line
  `[rebase-sweep <UTC-stamp>] dispatched=N rebased=N deferred=N`, then one `- PR #<n>: <reason>`
  line per deferral (deduped, order kept; deferred = number of lines). `--dry` and a missing
  `--record` post nothing; `dispatched != rebased + failed` exits 1 and posts nothing.
- `make rebase-sweep-record RECORD=<issue> DISPATCHED=/REBASED=/FAILED= [LINES=<file>]` is wired
  (mk/bots.mk, Makefile `.PHONY`, `scripts/package-layers.json` group entry).
- The `rebase-bot.yml` drain step counts `picked` (= rebased + failed), collects deferral lines
  from the sweep's `deferred=#<n>` numbers (reason taken from the matching pass-over line) plus
  failed picks into `$RUNNER_TEMP/rebase-sweep-lines.txt`, and exports `picked` as a step output.
  The new `Record the sweep summary on the tracker (issue #2950)` step posts `RECORD=2652`,
  guarded by `steps.drain.outputs.rebased != ''` so a crashed decision is never recorded as zeros.
- `tests/test_rebase_sweep_record.py` pins the summary shape, the quiet-pass record, the
  dedup, the dry/no-target/miscount silences, and the lane wiring (`RECORD=2652`, the guard,
  the make target, the layers entry).
- Live proof: the lane's recorder ran against the real board — see the `[rebase-sweep …]`
  comment id recorded in tasks.md and in #2950's `## Technical`.

## Key decisions

- The recorder is a separate script the lane calls, not `--record` threaded through the sweeper:
  `rebase_bot_sweep.py`'s decision logic stays pure (no posting side-effects in the decider).
- A deferral is anything this run leaves for the next run: UNKNOWN deferrals AND failed picks —
  `deferred` counts the lines, and `dispatched == rebased + failed` is enforced.
- A record failure reddens the record step (issue #312 loudness: a crashed decision is a FAILED
  step; a swallowed `|| echo ::warning::` fallback was caught by `test_bot_decision_loudness`).
