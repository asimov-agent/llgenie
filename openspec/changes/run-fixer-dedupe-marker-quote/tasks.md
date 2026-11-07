# Tasks

- [x] `scripts/run_failure_reactor.py::filed()` builds the `--search` phrase from the marker with
      double-quote characters stripped (a workflow display name like `says "no verdict" out loud`
      must not break the quoted phrase; GitHub search cannot nest a `"`).
- [x] A regression test drives a workflow whose display name contains a `"` through the reactor with
      a pre-existing same-marker issue and asserts no `issue create` happens (`--dry` run prints
      `already filed`).
- [x] The `gh` stub's `issue list` branch in `tests/test_run_failure_reactor.py` models GitHub's
      quoted-phrase rule, so the quoted-marker case is exercised for real and cannot silently regress.
- [x] Fast gates pass from the worktree: the reactor test suite (23/23 green) and
      `make openspec-validate NAME=run-fixer-dedupe-marker-quote`.
- [x] Live proof on the real board: `filed()` with the real marker (quotes stripped) finds the 9
      existing `judge@05185f9aecc9` issues; the exact-marker query returns 0 (the defect).
- [x] Docs trio: `docs/changes.d/2026-11-07-run-fixer-dedupe-marker-quote-1990.md` (one table row) +
      `agent-wiki/2026-11-07-run-fixer-dedupe-marker-quote-1990.md` narrative + regenerated `CHANGES.md`;
      `make check-docs` green.
- [x] PR opened against upstream `main` from the fork, carries `Issue: #1990` / `Fix:` / `Benefit:` /
      `Technical:` and the `AGENTS:` line; `closes #1990`.
