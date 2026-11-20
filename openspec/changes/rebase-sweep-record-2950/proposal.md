# Proposal: the rebase sweeper records its sweep summary on the #2652 tracker

## Why

Issue #2950 (the out-of-scope remainder of #2652, split out by PR #2951's lane). The two 30m
sweepers owe a greppable per-run summary to the rolling tracker #2652. The auto-merge sweeper got
its `--record` wiring in `sweep-record-2652`; the rebase side still has none. The `[rebase-sweep …]`
line was emitted by the Hermes cron planner prompt, banned 2026-11-14: the last record on #2652 is
`[rebase-sweep 2026-11-14T01:18Z] dispatched=0 rebased=0 deferred=0`, and live lane runs since
then print rebased/failed counts into an ephemeral step summary that dies with the run. A passing
rebase sweep and a stalled one look identical on the tracker.

## What Changes

- `scripts/rebase_bot_sweep.py` gains a structured deferral readout: each entry of the sweep's
  already-computed `deferred` list prints as its own `deferred=#<n>` line, so a lane (or a human)
  can count deferrals from stdout instead of parsing prose.
- NEW `scripts/rebase_sweep_record.py`: assembles and posts EXACTLY ONE summary comment on the
  target issue — first line `[rebase-sweep <UTC-stamp>] dispatched=<n> rebased=<n> deferred=<n>`,
  then one `- PR #<n>: <reason>` line per deferred/picked-but-failed PR (lines read from a
  lane-written file). `--dry` prints instead of posting. No `--record`, no comment.
- NEW `make rebase-sweep-record REPO=… RECORD=<issue> DISPATCHED=<n> REBASED=<n> FAILED=<n> LINES=<file>`
  wires the script.
- `.github/workflows/rebase-bot.yml`: the drain step counts `dispatched` (picks = rebased + failed)
  and accumulates deferral/failure lines into `$RUNNER_TEMP`; a new `Record the sweep on the
  tracker` step (`if: always()`, `RECORD=2652`) posts the summary via the make target. Dry and
  unrecorded paths post nothing; per-PR claim/done markers stay untouched.

## Out of Scope

- The per-PR rebase executor (`scripts/rebase_bot.py`), claim semantics, and the daily cap.
- Any Hermes host-cron or kanban revival.
