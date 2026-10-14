# Tasks

- [x] 1. Write the proposal + spec for the documentation mandate (issue #257).
- [x] 2. `AGENTS.md`: README + agent-wiki updates are part of every change, in the same commit,
      each naming the issue it answers.
- [x] 3. `scripts/check_docs.py` (`check` / `report`) + `make check-docs` / `make docs-report`,
      wired as the last step of `ci-unit`.
- [x] 4. `tests/fixtures/docs-exceptions.json` for targets that legitimately stay out, with a
      reason + date + issue, and a stale entry failing.
- [x] 5. `tests/test_check_docs.py`: the real tree is clean, the report shape, the CLI's check
      agrees with the library, whole-token matching, stale exceptions, and unreferenced records.
- [x] 6. Rebased onto `01c9944`; the gate's first real catch is fixed in this commit
      (`make issue-bot-image` from #249 was user-facing and undocumented), the two targets are
      declared `.PHONY`, and the help text cites this issue rather than the flaky-fetch one.
- [x] 7. Verify: the suite, `make check-docs`, `make lint`, `make check-wiring`,
      `openspec-validate NAME=docs-mandate`.
