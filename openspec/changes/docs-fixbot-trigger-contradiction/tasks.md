# docs-fixbot-trigger-contradiction — tasks

- [x] 1. OpenSpec change written (`.openspec.yaml`, `proposal.md`, `specs/docs-bots-fixbot-trigger/spec.md` with G/W/T + `- **Test:**` lines) before implementation
- [x] 2. Rewrite the `docs/BOTS.md:2613` fix-bot sentence to `workflow_dispatch`-only / manual-only, referencing owner directive 2026-11-08, #2293
- [x] 3. Verify no current-hourly-schedule description survives: `grep -n "fix-bot\.md.*schedule\|fix-bot.?\?.*hourly" docs/BOTS.md` returns only the explicit historical negations (lines 62-66 section and the `:17 slot is gone` line)
- [x] 4. `make lint` passes (verified via `python3 scripts/lint_linefeeds.py`: LINT OK)
- [x] 5. `make check-docs` passes (verified via `python3 scripts/check_docs.py check --root .`: 700 notes, all referenced + indexed)
- [x] 6. `make check-architecture-census` passes (verified via `python3 scripts/check_architecture_census.py check`: OK, census referent `7e633a28` ancestor of HEAD)
- [x] 7. Documentation trio: `agent-wiki/2026-11-09-docs-fixbot-trigger-contradiction-2322.md` + `docs/changes.d/2026-11-09-docs-fixbot-trigger-contradiction-2322.md` (indexed into `CHANGES.md` via `scripts/changes_index.py write`, row at line 19), keyed to issue #2322
- [x] 8. `make openspec-validate NAME=docs-fixbot-trigger-contradiction` — CLI requires a docker daemon that is unavailable in the agent container and could not run; the change directory is authored in the CLI's exact format (`.openspec.yaml`, `proposal.md`, `specs/…/spec.md` with G/W/T + `- **Test:**`, `tasks.md`) and the three runnable gates pass
