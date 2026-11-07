# bot-restore-health — tasks

- [x] 1. `scripts/bots_restore_health.py`: move `--repo` onto the `measure` subparser so the Makefile/docstring invocation `measure --repo owner/repo` parses (was top-level-only → `unrecognized arguments`)
- [x] 2. `tests/test_bots_restore_health.py`: hermetic tests — `measure --repo` accepted after the subcommand (RED on base parser, GREEN on fix), `measure` requires `--repo`, `restore` prints `restore_first` + `restore_after`
- [x] 3. Live restore: re-enable the 14 still-`disabled_manually` paused bots in recorded order on `asimov-agent/llgenie`, each verified `active` on the wire
- [x] 4. `docs/changes.d/2026-11-07-bot-restore.md` + `agent-wiki/2026-11-07-bot-restore.md` + `CHANGES.md` re-render
- [x] 5. Verification: `pytest tests/test_bots_restore_health.py` (3 passed), `make check-docs` (ok), `make changes-index`, `openspec validate`
