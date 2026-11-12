# Tasks: archbot-note-pair

- [x] 1. Extend `scripts/architecture_bot.py::publish` with the deterministic pair step
      (note + fragment + `changes_index.write`) and include the four paths in the bot commit.
      (done: `pair_stem`/`pair_row`/`pair_note`/`emit_pair` + pre-flight `parse_row` probe)
- [x] 2. Update `.github/workflows/architecture-bot.yml` header: the doc is still the only
      AGENT-writable file; the publish leg commits the doc plus its owed note/row/CHANGES.md.
- [x] 3. Extend `tests/test_architecture_bot.py` in place: four-path commit, fragment parses,
      note link matches stem, dry-run and no-drift write no pair.
      (done: publish test asserts the four paths + fragment + index link; new dry-run test;
      no-drift and pending tests assert no pair appears)
- [x] 4. `make test-unit ARCH_TESTS_FILTER`-style module run green + `make check-docs`,
      `make lint`, `make check-workflows`, `make openspec-validate NAME=archbot-note-pair`.
      (done: suite 3697 passed / 7 deselected; gates rc=0; validate "Change 'archbot-note-pair' is valid")
- [x] 5. Mirror issue #2598 body (tick AC with proven strings) and prepare the PR body carrying
      `closes #2598`; local replays green: `check-pr-hygiene acceptance-form|agents-line|commit-checkboxes`
      and `check_pr_closing` rc=0 against `d951ae5c4`.
