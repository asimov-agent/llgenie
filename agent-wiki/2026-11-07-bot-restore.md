# Bot-fleet restore: make the #902 measurement runnable and re-enable in recorded order (issue #1879)

## Problem

The 2026-10-28 bot pause (`bots/pause.toml`, issue #902, deliberate under runner starvation #817) is
correctly recorded, but the **restore is stale and out-of-order**: 14 of the 16 paused workflows
remain `disabled_manually` on the wire even though the queue has long since drained (recent PR jobs
reach `in_progress` within seconds, runs complete in under two minutes, no backlog), and the saved
restore order was violated — `restore_after` bots (security-scan, engine-build) were re-enabled while
`restore_first` bots (fix-bot, issue-dedupe, registry-sync) stayed dark. Worse, the restore could not
even be *measured*: `make bots-restore-health CMD=measure REPO=…` errored

```
bots_restore_health.py: error: unrecognized arguments: --repo asimov-agent/llgenie
```

because the Makefile and the script's docstring both pass `--repo` **after** the `measure`
subcommand while `argparse` declared it only on the **top-level** parser.

## Fix

1. `scripts/bots_restore_health.py`: `--repo` is now a `measure` **subparser** option (the docstring
   and Makefile already spell `measure --repo owner/repo`). `measure` now parses exactly as
   documented; `restore` needs no `--repo` and still prints the ordered list.
2. `tests/test_bots_restore_health.py`: new hermetic tests pin the CLI contract — `measure --repo` is
   accepted after the subcommand, `measure` without `--repo` refuses, and `restore` prints
   `restore_first` then `restore_after` from `bots/pause.toml`. The first test fails on the pre-fix
   parser (mutation-proved) and passes on the fix.
3. Live restore on `asimov-agent/llgenie`: the remaining `disabled_manually` paused bots are
   re-enabled in the recorded order (`restore_first` then `restore_after`), each verified `active` on
   the wire, and `make bots-restore-health CMD=measure` passes with the fleet re-enabled (AC-3).

## Why

The board wakes; the 46 open `agent:implement` issues regain their automated dispatch/refine/repair
paths; the fleet's restore machinery is proven working instead of half-delivered. The next reader
sees a restored fleet consistent with the recorded decision in `bots/pause.toml`.

Pinned by `tests/test_bots_restore_health.py`.
