# bot-restore-health — spec delta

Capability: `bot-restore-health`
Issue: [#1879](https://github.com/asimov-agent/llgenie/issues/1879)

## ADDED Requirements

### Requirement: the restore-condition measurement parses its documented CLI

The `bots-restore-health` measurement SHALL accept `--repo` after the `measure` subcommand, exactly
as its own docstring and the Makefile target invoke it, so `make bots-restore-health CMD=measure
REPO=owner/repo` can run (it previously errored `unrecognized arguments: --repo` because `--repo`
was declared only on the top-level parser).

WHEN a caller runs `bots_restore_health.py measure --repo owner/repo`,
THEN it SHALL sample the queue and return 0 when healthy / 1 when stuck, and SHALL NOT fail on
argument order.

#### Scenario: the documented measure invocation runs
Given the Makefile target `bots-restore-health` with `CMD=measure REPO=owner/repo`,
When   the invocation `bots_restore_health.py "measure" --repo "owner/repo"` is parsed,
Then   it SHALL succeed (not raise `unrecognized arguments: --repo`).

### Requirement: restore prints restore_first then restore_after

The `restore` command SHALL print `bots/pause.toml`'s `restore_first` list followed by `restore_after`
in order, so the restore re-enables the cheap common bots first and the heaviest last (the #902
decision).

WHEN a caller runs `bots_restore_health.py restore`,
THEN it SHALL print one workflow per line: `restore_first` then `restore_after`.

#### Scenario: restore prints the recorded order
Given `bots/pause.toml` declares `restore_first = ["fix-bot", ...]` then `restore_after = ["security-scan", ...]`,
When   a caller runs `bots_restore_health.py restore`,
Then   the first lines are `fix-bot` (and the rest of `restore_first`) followed by `security-scan` (and the rest of `restore_after`), one per line.
