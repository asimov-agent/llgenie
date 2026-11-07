# bot-restore-health — proposal

Issue: [#1879](https://github.com/asimov-agent/llgenie/issues/1879)

## Why

The 2026-10-28 bot pause (`bots/pause.toml`, issue #902) was deliberate under runner starvation
(#817) and is correctly recorded, but the restore was stale, out-of-order, and — worst — could not
be **measured**: `make bots-restore-health CMD=measure REPO=…` errored
`bots_restore_health.py: error: unrecognized arguments: --repo asimov-agent/llgenie` because the
Makefile (L904) and the script's docstring (L24) both pass `--repo` AFTER the `measure` subcommand,
while argparse declared `--repo` only on the TOP-LEVEL parser. A restore condition you cannot measure
is a control you cannot trust: 14 of 16 paused workflows stayed `disabled_manually` out-of-order and
the queue-health proof that gates the restore could never run.

## What Changes

- **`scripts/bots_restore_health.py`**: `--repo` moves onto the `measure` subparser (the invocation
  the Makefile and docstring already spell: `measure --repo owner/repo`). `measure` now parses
  exactly as documented; `restore` needs no `--repo` and still prints the ordered restore list.
- **`tests/test_bots_restore_health.py`**: hermetic tests pin the CLI contract — `measure --repo`
  accepted after the subcommand (fails on the base parser, passes on the fix), `measure` requires
  `--repo`, and `restore` prints `restore_first` then `restore_after` from `bots/pause.toml`.
- **Live restore** (the wire half): the remaining `disabled_manually` paused bots are re-enabled in
  the recorded order (`restore_first` then `restore_after`), each verified `active` on the wire, and
  the queue-health measurement passes with the fleet back on (AC-2/AC-3).
- **`docs/changes.d/2026-11-07-bot-restore.md`** + `agent-wiki/2026-11-07-bot-restore.md`: the
  change-note pair the docs gate requires.
